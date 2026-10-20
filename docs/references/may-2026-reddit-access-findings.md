# May 2026 Reddit Access Findings

## Observed Blocking Patterns (May 2026)

During testing in May 2026, the following blocking patterns were observed:

### r/BabyBumps
- RSS feed accessible: `https://old.reddit.com/r/BabyBumps/.rss?limit=10` 
- JSON/HTML endpoints blocked with network security pages

### r/NewParents, r/pumping, r/Breastfeeding
- All access methods (JSON, RSS, HTML) consistently blocked with network security pages

## Recommended Workarounds

1. **Prioritize r/BabyBumps via RSS feed** - Most reliable Reddit data source as of May 2026
2. **Consider alternative approaches for production use:**
   - Use Reddit's official API with OAuth2 authentication
   - Utilize third-party services like Pushshift.io (verify current status)
   - Employ residential proxy services to rotate IP addresses
   - Schedule requests during low-traffic periods with exponential backoff
   - Explore purchasing access to Reddit's enterprise API

## Current Implementation

The script implements comprehensive fallback mechanisms:
1. Hermes browser tool (if available)
2. Direct HTTP requests with rotating User-Agents
3. RSS feed fallbacks
4. Error handling to continue with available data when requests fail

Given the blocking patterns, users should expect significant data loss from subreddits other than r/BabyBumps.