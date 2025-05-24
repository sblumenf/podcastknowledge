# Google Colab Adaptation Guide for podcast_knowledge_system_enhanced.py

## Overview
This guide details the specific modifications needed to effectively run the podcast knowledge system in Google Colab, addressing Colab's unique constraints and leveraging its capabilities.

## Key Colab Constraints to Address
1. **12-24 hour runtime limits** (disconnections)
2. **Ephemeral storage** (data loss on disconnect)
3. **Limited memory** (~12GB RAM, varies by GPU)
4. **No persistent local filesystem**
5. **Interactive notebook environment**
6. **GPU availability fluctuations**

## Required Modifications

### 1. Google Drive Integration & Persistence

#### Current Code (Lines ~150-300 in PodcastConfig):
```python
BASE_DIR = os.getenv("PODCAST_DIR", ".")
AUDIO_DIR = f"{BASE_DIR}/audio"
OUTPUT_DIR = f"{BASE_DIR}/output"
```

#### Colab Modification:
```python
# Add at top of configuration section
from google.colab import drive
drive.mount('/content/drive')

# Modify PodcastConfig class
class PodcastConfig:
    # Colab-specific paths
    COLAB_MODE = 'google.colab' in sys.modules
    
    if COLAB_MODE:
        BASE_DIR = "/content/drive/MyDrive/podcast_knowledge"
        # Ensure persistence across sessions
        os.makedirs(BASE_DIR, exist_ok=True)
    else:
        BASE_DIR = os.getenv("PODCAST_DIR", ".")
    
    AUDIO_DIR = f"{BASE_DIR}/audio"
    OUTPUT_DIR = f"{BASE_DIR}/output"
    CHECKPOINT_DIR = f"{BASE_DIR}/checkpoints"
    CACHE_DIR = f"{BASE_DIR}/cache"
    
    # Create all directories
    for dir_path in [AUDIO_DIR, OUTPUT_DIR, CHECKPOINT_DIR, CACHE_DIR]:
        os.makedirs(dir_path, exist_ok=True)
```

### 2. Enhanced Checkpoint System

#### Add Checkpoint Manager Class (after line ~300):
```python
class ColabCheckpointManager:
    """Manages checkpoints for Colab session recovery."""
    
    def __init__(self, checkpoint_dir=None):
        self.checkpoint_dir = checkpoint_dir or PodcastConfig.CHECKPOINT_DIR
        self.checkpoint_file = os.path.join(self.checkpoint_dir, "colab_checkpoint.json")
        self.progress_file = os.path.join(self.checkpoint_dir, "progress.json")
        
    def save_checkpoint(self, state):
        """Save current processing state."""
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'state': state,
            'environment': {
                'gpu_available': torch.cuda.is_available() if torch else False,
                'memory_used': self._get_memory_usage()
            }
        }
        
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
            
    def load_checkpoint(self):
        """Load last checkpoint if exists."""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                return json.load(f)
        return None
        
    def save_progress(self, podcast_name, episodes_completed, current_episode=None):
        """Track processing progress."""
        progress = self.load_progress() or {}
        
        if podcast_name not in progress:
            progress[podcast_name] = {
                'episodes_completed': [],
                'last_episode': None,
                'total_processed': 0
            }
            
        progress[podcast_name]['episodes_completed'].extend(episodes_completed)
        progress[podcast_name]['last_episode'] = current_episode
        progress[podcast_name]['total_processed'] = len(progress[podcast_name]['episodes_completed'])
        progress['last_updated'] = datetime.now().isoformat()
        
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
            
    def load_progress(self):
        """Load progress tracking."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return None
        
    def _get_memory_usage(self):
        """Get current memory usage stats."""
        import psutil
        process = psutil.Process()
        return {
            'ram_mb': process.memory_info().rss / 1024 / 1024,
            'gpu_mb': torch.cuda.memory_allocated() / 1024 / 1024 if torch and torch.cuda.is_available() else 0
        }
```

### 3. Memory Management Enhancements

#### Modify cleanup_memory function (around line ~1900):
```python
def cleanup_memory(force=False):
    """Enhanced memory cleanup for Colab."""
    import psutil
    
    # Get memory usage before cleanup
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024
    
    # Standard cleanup
    gc.collect()
    
    # GPU cleanup
    if torch and torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    
    # Matplotlib cleanup
    if 'matplotlib' in sys.modules:
        import matplotlib.pyplot as plt
        plt.close('all')
    
    # Force cleanup if memory usage is high
    if force or mem_before > 8000:  # 8GB threshold
        # Clear module caches
        if hasattr(sys, 'modules'):
            modules_to_clear = ['transformers', 'whisper', 'pyannote']
            for module in modules_to_clear:
                if module in sys.modules:
                    del sys.modules[module]
        
        # Additional aggressive cleanup
        gc.collect(2)  # Full collection
        
    # Log memory freed
    mem_after = process.memory_info().rss / 1024 / 1024
    if mem_before - mem_after > 100:  # If freed more than 100MB
        logging.info(f"Memory cleanup freed {mem_before - mem_after:.0f}MB")
```

### 4. Colab-Specific Audio Download with Caching

#### Modify download_audio function (around line ~2300):
```python
def download_audio(url, output_path, use_cache=True):
    """Download audio with Colab-optimized caching."""
    if PodcastConfig.COLAB_MODE and use_cache:
        # Use content-based cache key
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cache_path = os.path.join(PodcastConfig.CACHE_DIR, f"{cache_key}.mp3")
        
        # Check cache first
        if os.path.exists(cache_path):
            logging.info(f"Using cached audio: {cache_key}")
            # Copy from cache to output path
            import shutil
            shutil.copy2(cache_path, output_path)
            return output_path
    
    # Download with progress for Colab
    try:
        from tqdm.notebook import tqdm  # Use notebook version in Colab
        
        response = urllib.request.urlopen(url)
        total_size = int(response.headers.get('Content-Length', 0))
        
        with open(output_path, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    pbar.update(len(chunk))
                    
        # Save to cache if in Colab
        if PodcastConfig.COLAB_MODE and use_cache:
            import shutil
            shutil.copy2(output_path, cache_path)
            
    except Exception as e:
        logging.error(f"Download failed: {e}")
        raise
        
    return output_path
```

### 5. Session Recovery & Auto-Resume

#### Add to PodcastKnowledgePipeline.__init__ (around line ~7245):
```python
class PodcastKnowledgePipeline:
    def __init__(self, config=None):
        self.config = config or PodcastConfig()
        
        # Add Colab-specific initialization
        if self.config.COLAB_MODE:
            self.checkpoint_manager = ColabCheckpointManager()
            self._setup_colab_environment()
            self._check_resume_state()
            
    def _setup_colab_environment(self):
        """Setup Colab-specific environment."""
        # Set up GPU
        if torch and torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(0.8)  # Leave some memory for system
            
        # Configure for notebook display
        if 'IPython' in sys.modules:
            from IPython.display import display, HTML
            self.display = display
            self.HTML = HTML
            
    def _check_resume_state(self):
        """Check if we should resume from checkpoint."""
        checkpoint = self.checkpoint_manager.load_checkpoint()
        if checkpoint:
            time_diff = datetime.now() - datetime.fromisoformat(checkpoint['timestamp'])
            if time_diff.total_seconds() < 86400:  # Less than 24 hours old
                print(f"Found checkpoint from {checkpoint['timestamp']}")
                print("Would you like to resume? (y/n)")
                if input().lower() == 'y':
                    self.resume_state = checkpoint['state']
                else:
                    self.resume_state = None
```

### 6. Progress Visualization for Notebooks

#### Add progress display function (after visualization section ~2800):
```python
def display_progress_notebook(current, total, message="Processing"):
    """Display progress in Colab notebook."""
    if 'IPython' in sys.modules:
        from IPython.display import display, HTML, clear_output
        
        progress_percent = (current / total) * 100
        bar_length = 50
        filled_length = int(bar_length * current / total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        html = f"""
        <div style="margin: 10px 0;">
            <div style="font-weight: bold; margin-bottom: 5px;">
                {message}: {current}/{total} ({progress_percent:.1f}%)
            </div>
            <div style="background-color: #f0f0f0; border-radius: 5px;">
                <div style="background-color: #4CAF50; width: {progress_percent}%; 
                            padding: 5px 0; border-radius: 5px; text-align: center; 
                            color: white; font-weight: bold;">
                    {progress_percent:.0f}%
                </div>
            </div>
        </div>
        """
        
        clear_output(wait=True)
        display(HTML(html))
```

### 7. API Rate Limiting with Visual Feedback

#### Modify HybridRateLimiter._get_wait_time (around line ~1800):
```python
def _get_wait_time(self):
    """Calculate wait time with Colab progress display."""
    current_time = time.time()
    min_wait = float('inf')
    
    for model_name, usage in self.requests.items():
        if usage['minute']:
            wait = 61 - (current_time - usage['minute'][0])
            min_wait = min(min_wait, wait)
    
    wait_seconds = max(1, int(min_wait))
    
    # Visual countdown in Colab
    if PodcastConfig.COLAB_MODE and 'IPython' in sys.modules:
        from IPython.display import clear_output
        import time
        
        for remaining in range(wait_seconds, 0, -1):
            clear_output(wait=True)
            print(f"⏳ Rate limit cooldown: {remaining} seconds remaining...")
            print(f"{'█' * (remaining // 2)}")
            time.sleep(1)
        clear_output(wait=True)
        print("✅ Ready to continue!")
    else:
        time.sleep(wait_seconds)
    
    return wait_seconds
```

### 8. Simplified Entry Point for Colab

#### Add at the end of file (after line ~8179):
```python
def colab_process_podcast(podcast_name, rss_url=None, num_episodes=5, resume=True):
    """
    Simplified entry point for Colab users.
    
    Args:
        podcast_name: Name of podcast or key from PODCAST_FEEDS
        rss_url: Optional RSS URL if not in PODCAST_FEEDS
        num_episodes: Number of episodes to process
        resume: Whether to resume from checkpoint
        
    Returns:
        Summary statistics dict
    """
    # Setup logging for Colab
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{PodcastConfig.OUTPUT_DIR}/colab_process.log')
        ]
    )
    
    # Initialize pipeline
    pipeline = PodcastKnowledgePipeline()
    
    # Check for resume
    if resume and pipeline.checkpoint_manager:
        progress = pipeline.checkpoint_manager.load_progress()
        if progress and podcast_name in progress:
            completed = progress[podcast_name]['episodes_completed']
            print(f"Found {len(completed)} previously processed episodes")
            print("Resuming from checkpoint...")
    
    # Get RSS URL
    if not rss_url:
        rss_url = PODCAST_FEEDS.get(podcast_name)
        if not rss_url:
            raise ValueError(f"Unknown podcast: {podcast_name}")
    
    # Process with progress tracking
    try:
        summary = pipeline.process_podcast(
            podcast_name=podcast_name,
            rss_url=rss_url,
            max_episodes=num_episodes
        )
        
        # Display summary in notebook
        if 'IPython' in sys.modules:
            from IPython.display import display, HTML
            
            html = f"""
            <div style="border: 2px solid #4CAF50; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h2>✅ Processing Complete!</h2>
                <ul>
                    <li><b>Podcast:</b> {podcast_name}</li>
                    <li><b>Episodes Processed:</b> {summary.get('episodes_processed', 0)}</li>
                    <li><b>Total Insights:</b> {summary.get('total_insights', 0)}</li>
                    <li><b>Total Entities:</b> {summary.get('total_entities', 0)}</li>
                    <li><b>Processing Time:</b> {summary.get('total_time', 0):.1f} minutes</li>
                </ul>
            </div>
            """
            display(HTML(html))
            
        return summary
        
    except Exception as e:
        logging.error(f"Processing failed: {e}")
        # Save checkpoint on failure
        if pipeline.checkpoint_manager:
            pipeline.checkpoint_manager.save_checkpoint({
                'podcast_name': podcast_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        raise

# Colab-friendly podcast feed dictionary
PODCAST_FEEDS = {
    'my-first-million': 'https://feeds.megaphone.fm/HSW7835889191',
    'all-in': 'https://feeds.megaphone.fm/all-in-with-chamath-jason-sacks-friedberg',
    'lex-fridman': 'https://lexfridman.com/feed/podcast/',
    'tim-ferriss': 'https://rss.art19.com/tim-ferriss-show',
    'huberman-lab': 'https://feeds.megaphone.fm/hubermanlab',
}
```

### 9. Environment Setup Function for Colab

#### Add setup function:
```python
def setup_colab_environment():
    """One-click setup for Colab environment."""
    print("🚀 Setting up Colab environment...")
    
    # Install required packages
    packages = [
        'neo4j',
        'feedparser', 
        'python-dotenv',
        'langchain-google-genai',
        'faster-whisper',
        'pyannote.audio',
        'torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118'
    ]
    
    for package in packages:
        print(f"Installing {package}...")
        os.system(f"pip install -q {package}")
    
    # Mount Google Drive
    from google.colab import drive
    drive.mount('/content/drive')
    
    # Setup API keys from Colab secrets
    from google.colab import userdata
    
    required_keys = ['NEO4J_URI', 'NEO4J_PASSWORD', 'GOOGLE_API_KEY', 'HF_TOKEN']
    for key in required_keys:
        try:
            os.environ[key] = userdata.get(key)
            print(f"✅ {key} loaded from secrets")
        except:
            print(f"⚠️ {key} not found in secrets")
    
    print("\n✅ Environment setup complete!")
    return True
```

## Usage in Colab

```python
# Cell 1: Setup
!wget https://raw.githubusercontent.com/[your-repo]/podcast_knowledge_system_enhanced.py
import podcast_knowledge_system_enhanced as pks

# Cell 2: Configure environment  
pks.setup_colab_environment()

# Cell 3: Process podcast
summary = pks.colab_process_podcast(
    podcast_name='my-first-million',
    num_episodes=5,
    resume=True  # Will resume if disconnected
)
```

## Key Benefits of These Modifications

1. **Automatic resume** after disconnections
2. **Persistent storage** in Google Drive
3. **Visual progress** tracking in notebooks
4. **Memory optimization** for limited resources
5. **Smart caching** to avoid re-downloading
6. **Graceful handling** of GPU availability
7. **Rate limit visualization** with countdown
8. **One-click setup** function
9. **Checkpoint system** for long runs
10. **Notebook-friendly** output formatting