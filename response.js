[
  {
    analysis_id: "snapshot_1735683600_So11111",
    token_address: "So11111111111111111111111111111111111111112",
    timestamp: "2024-12-31T12:00:00Z",
    source_event: "snapshot_scheduled",
    analysis_type: "snapshot",
    snapshot_generation: 1, // Increments with each update
    warnings: [],
    errors: [],
    data_sources: ["birdeye", "helius", "solanafm", "dexscreener"],

    service_responses: {
      birdeye: {
        /* Birdeye API response */
      },
      helius: {
        /* Helius API response */
      },
      solanafm: {
        /* SolanaFM API response */
      },
      dexscreener: {
        /* DexScreener API response */
      },
    },

    security_analysis: {
      security_status: "safe",
      overall_safe: true,
      critical_issues: [],
      warnings: [],
      note: "Security validation bypassed for snapshot",
    },

    overall_analysis: {
      score: 75.5,
      risk_level: "low",
      recommendation: "consider",
      confidence: 85.0,
      confidence_score: 85.0,
      summary: "Snapshot analysis from 4 market sources",
      positive_signals: ["Market data available", "Trading activity present"],
      risk_factors: [],
      security_passed: true, // Always true for snapshots
      services_analyzed: 4,

      // Enhanced metrics (same as comprehensive analysis)
      volatility: {
        recent_volatility_percent: 12.5,
        volatility_available: true,
        volatility_risk: "medium",
      },
      whale_analysis: {
        whale_count: 3,
        whale_control_percent: 25.5,
        top_whale_percent: 15.2,
        whale_risk_level: "medium",
      },
      sniper_detection: {
        sniper_risk: "low",
        pattern_detected: false,
        similar_holders: 2,
      },
      market_structure: {
        data_sources: 4,
        has_price_data: true,
        has_volume_data: true,
        has_liquidity_data: true,
      },
    },

    metadata: {
      processing_time_seconds: 8.5,
      data_sources_available: 4,
      services_attempted: 4,
      services_successful: 4,
      security_check_passed: true, // Always true
      analysis_stopped_at_security: false, // Always false
      ai_analysis_completed: false,
      snapshot_update: true,
      previous_snapshot_id: "snapshot_1735680000_So11111",
    },

    docx_cache_key: "snapshot_1735683600_So11111",
    docx_expires_at: "2024-12-31T15:00:00Z",
  },
];
