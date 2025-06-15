
MANUAL YOUTUBE URL VERIFICATION GUIDE
=====================================

To manually verify that YouTube URLs navigate to correct positions:

1. SETUP:
   - Use a real YouTube video URL (replace 'test123' with actual video ID)
   - Ensure the video is longer than the test timestamps
   - Use a video you can easily identify content at specific times

2. TEST CASES TO VERIFY:

   Test 1 - Unit unit_1:
   - Expected time: 118.0s (1:58)
   - URL pattern: ...&t=118s
   - Verification: Video should start at 1:58
   - Description: Normal discussion

   Test 2 - Unit unit_2:
   - Expected time: 0s (0:00)
   - URL pattern: ...&t=0s
   - Verification: Video should start at 0:00
   - Description: Early introduction

   Test 3 - Unit unit_3:
   - Expected time: 0s (0:00)
   - URL pattern: ...&t=0s
   - Verification: Video should start at 0:00
   - Description: Boundary explanation

   Test 4 - Unit unit_4:
   - Expected time: 3659.0s (1:00:59)
   - URL pattern: ...&t=3659s
   - Verification: Video should start at 1:00:59
   - Description: Late conclusion

3. VERIFICATION STEPS:
   a. Replace 'test123' in URLs with real YouTube video ID
   b. Click each URL in a browser
   c. Verify video starts at expected timestamp
   d. Confirm -2 second adjustment provides good context
   e. Check that minimum 0 second handling works correctly

4. EXPECTED BEHAVIOR:
   - All URLs should navigate to correct video positions
   - Timestamps should provide 2 seconds of context before actual start
   - No URL should have negative timestamps (minimum 0 enforced)
   - URL format should be simple: ...&t=XXXs

5. SUCCESS CRITERIA:
   ✅ Video starts within 1 second of expected timestamp
   ✅ Content provides appropriate context
   ✅ No technical errors or invalid URLs
   ✅ Simple URL construction works reliably
