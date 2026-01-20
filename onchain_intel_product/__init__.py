"""
OnChain Intelligence Data Product v1.0.0

KNOWN FAILURE MODES:

1. DATABASE CONNECTIVITY FAILURES
   - Symptom: All requests return 500 errors
   - Cause: Database connection lost or credentials invalid
   - Mitigation: Health checks, connection pooling, retry logic
   - Response: System automatically blocks all data (state=BLOCKED)

2. STALE DATA CONDITIONS  
   - Symptom: data_lag=true, state=BLOCKED
   - Cause: Upstream data pipeline delays or failures
   - Mitigation: Pipeline monitoring, data freshness alerts
   - Response: Automatic blocking until fresh data available

3. SIGNAL CALCULATION FAILURES
   - Symptom: invariants_passed=false, deterministic=false
   - Cause: Corrupted input data or calculation engine bugs
   - Mitigation: Comprehensive input validation, calculation verification
   - Response: Immediate blocking, audit trail preservation

4. CONFIGURATION DRIFT
   - Symptom: Inconsistent responses for same inputs over time
   - Cause: Configuration changes without proper versioning
   - Mitigation: Configuration hashing, immutable deployments
   - Response: Audit endpoint reveals config changes

5. MEMORY/RESOURCE EXHAUSTION
   - Symptom: Slow responses, timeouts, 500 errors
   - Cause: High load, memory leaks, inefficient queries
   - Mitigation: Resource monitoring, query optimization, rate limiting
   - Response: Graceful degradation, circuit breaker activation

6. SIGNAL CONFLICT SCENARIOS
   - Symptom: signal_conflict=true, state=DEGRADED
   - Cause: Contradictory signals from different detection engines
   - Mitigation: Signal correlation analysis, conflict resolution rules
   - Response: Reduced confidence weighting, explicit conflict flagging

7. VERIFICATION SYSTEM FAILURES
   - Symptom: All verification checks fail simultaneously
   - Cause: Verification engine malfunction or corrupted test data
   - Mitigation: Verification system monitoring, fallback verification
   - Response: Complete data blocking until verification restored

8. API AUTHENTICATION BYPASS
   - Symptom: Unauthorized access to sensitive endpoints
   - Cause: Authentication middleware failure or misconfiguration
   - Mitigation: Multiple authentication layers, access logging
   - Response: Immediate service shutdown, security incident response

9. AUDIT TRAIL CORRUPTION
   - Symptom: Audit hashes don't match, replay failures
   - Cause: Database corruption, hash algorithm changes
   - Mitigation: Hash verification, backup audit systems
   - Response: Compliance violation alerts, manual investigation

10. KILL SWITCH LOGIC BYPASS
    - Symptom: BLOCKED data incorrectly marked as ACTIVE
    - Cause: Kill switch logic bugs or configuration errors
    - Mitigation: Kill switch unit tests, integration tests
    - Response: Emergency service shutdown, manual override

CRITICAL PRINCIPLE: When in doubt, BLOCK. Incorrect blocking is acceptable, incorrect allowing is not.
"""

__version__ = "1.0.0"
__product__ = "onchain_intelligence"