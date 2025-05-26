SLO Management Guide
==================

This guide covers Service Level Objectives (SLOs) and Service Level Indicators (SLIs) for the Podcast Knowledge Pipeline.

Overview
--------

Service Level Objectives define the reliability targets for our service. They help us:

* Balance feature development with reliability work
* Make data-driven decisions about system changes
* Communicate expectations with stakeholders
* Prioritize incidents based on user impact

SLO Definitions
--------------

Availability SLO
~~~~~~~~~~~~~~~

* **Target**: 99.5% of episodes processed successfully
* **Measurement Window**: 30 days rolling
* **Error Budget**: 216 minutes per month

.. code-block:: yaml

   # Good event: Episode processed successfully
   # Bad event: Episode processing failed
   
   SLI = (successful_episodes / total_episodes) * 100

Latency SLOs
~~~~~~~~~~~

Episode Processing Latency
^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Target**: 95% of episodes processed within 5 minutes
* **Measurement**: 95th percentile processing time
* **Threshold**: 300 seconds

API Response Time
^^^^^^^^^^^^^^^^

* **Target**: 99% of API requests respond within 1 second
* **Measurement**: 99th percentile response time
* **Threshold**: 1000ms

Throughput SLO
~~~~~~~~~~~~~

* **Target**: Process at least 50 episodes per hour
* **Measurement Window**: 6 hours rolling
* **Success Criteria**: 95% of time windows meet target

Quality SLOs
~~~~~~~~~~~

Transcription Quality
^^^^^^^^^^^^^^^^^^^

* **Target**: 95% of transcriptions achieve 85%+ accuracy score
* **Measurement**: Median quality score per hour
* **Quality Threshold**: 0.85

Entity Extraction
^^^^^^^^^^^^^^^^

* **Target**: 90% of episodes extract at least 5 entities
* **Measurement**: Entities per episode ratio
* **Minimum Threshold**: 5 entities

Error Budget Management
----------------------

Error Budget Calculation
~~~~~~~~~~~~~~~~~~~~~~~

Error budget represents the amount of unreliability we can "afford" while still meeting our SLO:

.. code-block:: python

   # Monthly error budget (in minutes)
   error_budget = total_minutes * (100 - slo_target) / 100
   
   # For 99.5% availability over 30 days:
   error_budget = 43200 * 0.5 / 100 = 216 minutes

Burn Rate Alerts
~~~~~~~~~~~~~~~

We use multi-window burn rate alerts to detect issues early:

**Fast Burn (Critical)**
   * 1-hour burn rate > 2%
   * 6-hour burn rate > 1%
   * Action: Page on-call engineer

**Slow Burn (Warning)**
   * 6-hour burn rate > 5%
   * 24-hour burn rate > 2%
   * Action: Create ticket for investigation

Error Budget Policies
~~~~~~~~~~~~~~~~~~~

**80% Budget Consumed**
   * Freeze non-critical changes
   * Focus on reliability improvements
   * Review recent changes for issues

**100% Budget Exhausted**
   * Freeze all changes
   * Initiate incident response
   * All hands on reliability

Dashboard Usage
--------------

Accessing SLO Dashboard
~~~~~~~~~~~~~~~~~~~~~~

1. Navigate to Grafana: http://localhost:3000
2. Select "Podcast Knowledge Graph - SLO Dashboard"
3. Key panels:
   
   * **Availability Gauge**: Current SLI vs target
   * **Error Budget**: Remaining budget percentage
   * **Burn Rates**: Multi-window burn rate visualization
   * **SLO Summary**: 30-day compliance overview

Key Metrics to Monitor
~~~~~~~~~~~~~~~~~~~~

1. **Error Budget Remaining**: Should stay above 20%
2. **Burn Rate Alerts**: Watch for fast/slow burn indicators
3. **Composite SLOs**: Overall reliability and quality scores

SLI Queries
----------

Common Prometheus queries for SLI calculation:

.. code-block:: promql

   # Availability SLI (30 days)
   sum(increase(podcast_kg_episodes_processed_total[30d])) / 
   (sum(increase(podcast_kg_episodes_processed_total[30d])) + 
    sum(increase(podcast_kg_episodes_failed_total[30d])))

   # Episode processing latency (p95)
   histogram_quantile(0.95, 
     sum(rate(podcast_kg_processing_duration_seconds_bucket{stage="full_episode"}[5m])) 
     by (le)
   )

   # Throughput (episodes/hour)
   sum(rate(podcast_kg_episodes_processed_total[1h])) * 3600

   # Error budget burn rate (1 hour)
   1 - (sum(increase(podcast_kg_episodes_processed_total[1h])) / 
        (sum(increase(podcast_kg_episodes_processed_total[1h])) + 
         sum(increase(podcast_kg_episodes_failed_total[1h]))))

Implementing SLOs in Code
------------------------

Using the Error Budget Tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.core.error_budget import get_error_budget_tracker

   # Initialize tracker
   tracker = get_error_budget_tracker()

   # Register SLO
   tracker.register_slo(
       name="availability",
       description="Episode processing availability",
       target=99.5,
       measurement_window_days=30
   )

   # Calculate current status
   status = tracker.calculate_error_budget_status(
       slo_name="availability",
       current_sli=99.2,
       good_events=9920,
       total_events=10000,
       time_range_hours=720
   )

   # Check if we're burning too fast
   if status.is_burning_fast:
       print(f"Alert! Fast burn detected: {status.burn_rate_1h:.2%}/hour")

Integrating with Metrics
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from src.api.metrics import get_metrics_collector

   collector = get_metrics_collector()

   # Track successful processing
   collector.episodes_processed.inc()

   # Track failures
   collector.episodes_failed.inc()

   # Record processing time
   collector.processing_duration.observe(
       processing_time_seconds,
       labels={"stage": "full_episode"}
   )

Best Practices
-------------

1. **Review SLOs Monthly**
   
   * Analyze if targets are too aggressive or too loose
   * Adjust based on user feedback and business needs
   * Document changes and rationale

2. **Incident Response**
   
   * Check SLO dashboard first during incidents
   * Prioritize based on error budget impact
   * Document SLO violations in postmortems

3. **Feature Development**
   
   * Consider SLO impact before major changes
   * Run load tests to validate performance
   * Monitor burn rate after deployments

4. **Communication**
   
   * Share SLO status in weekly reports
   * Educate team on error budget concept
   * Celebrate reliability improvements

Troubleshooting
--------------

Common Issues
~~~~~~~~~~~~

**"SLI queries returning no data"**
   Check that metrics are being exported correctly:
   
   .. code-block:: bash
   
      curl http://localhost:8000/metrics | grep podcast_kg_

**"Error budget burn rate too high"**
   1. Check recent deployments
   2. Review provider health
   3. Analyze error logs
   4. Scale resources if needed

**"Dashboard not updating"**
   1. Verify Prometheus is scraping metrics
   2. Check recording rules are evaluated
   3. Restart Prometheus if needed

References
----------

* `Google SRE Book - SLO Chapter <https://sre.google/sre-book/service-level-objectives/>`_
* `The Art of SLOs <https://sre.google/workbook/implementing-slos/>`_
* `Error Budget Policy Examples <https://sre.google/workbook/error-budget-policy/>`_