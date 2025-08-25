console.log("🚀 Solana Token Analysis AI - Frontend Loaded");

// Global state management
window.SolanaAI = {
  config: {
    apiBaseUrl: "",
    version: "1.0.0",
    wsUrl: null,
  },
  state: {
    connected: false,
    notifications: [],
    systemHealth: null,
    currentUser: null,
  },
  utils: {},
  api: {},
  analysis: {}, // Add analysis module
  ws: null,
};

// Utility functions (enhanced with null safety)
window.SolanaAI.utils = {
  // Format numbers with K/M/B suffixes
  formatNumber(num) {
    if (!num && num !== 0) return "0";
    const value = parseFloat(num);
    if (isNaN(value)) return "0";
    if (value >= 1e9) return (value / 1e9).toFixed(2) + "B";
    if (value >= 1e6) return (value / 1e6).toFixed(2) + "M";
    if (value >= 1e3) return (value / 1e3).toFixed(2) + "K";
    return value.toFixed(2);
  },

  // Format percentage with + sign
  formatPercent(num) {
    if (!num && num !== 0) return "0%";
    const value = parseFloat(num);
    if (isNaN(value)) return "0%";
    return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
  },

  // Validate Solana address
  isValidSolanaAddress(address) {
    if (!address || typeof address !== "string") return false;
    if (address.length < 32 || address.length > 44) return false;
    return /^[1-9A-HJ-NP-Za-km-z]+$/.test(address);
  },

  // Copy to clipboard
  async copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.error("Failed to copy to clipboard:", err);
      return false;
    }
  },

  // Generate random ID
  generateId() {
    return Math.random().toString(36).substr(2, 9);
  },

  // Debounce function
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Format timestamp
  formatTime(timestamp) {
    if (!timestamp) return "N/A";

    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;

      if (diff < 60000) return "Just now";
      if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
      return date.toLocaleDateString();
    } catch (error) {
      return "Invalid date";
    }
  },

  // Show loading state
  showLoading(element, message = "Loading...") {
    if (typeof element === "string") {
      element = document.querySelector(element);
    }
    if (element) {
      element.innerHTML = `
        <div class="flex items-center justify-center py-4">
          <div class="loading-spinner mr-2"></div>
          <span class="text-gray-600">${message}</span>
        </div>
      `;
    }
  },

  // Show error state
  showError(element, message = "An error occurred") {
    if (typeof element === "string") {
      element = document.querySelector(element);
    }
    if (element) {
      element.innerHTML = `
        <div class="flex items-center justify-center py-4 text-red-600">
          <i class="fas fa-exclamation-triangle mr-2"></i>
          <span>${message}</span>
        </div>
      `;
    }
  },

  // Format currency values
  formatCurrency(value, decimals = 6) {
    if (!value && value !== 0) return "N/A";
    const num = parseFloat(value);
    if (isNaN(num)) return "N/A";
    return num.toFixed(decimals);
  },

  // Truncate address for display
  truncateAddress(address, startChars = 8, endChars = 8) {
    if (!address) return "N/A";
    if (address.length <= startChars + endChars) return address;
    return `${address.substring(0, startChars)}...${address.substring(
      address.length - endChars
    )}`;
  },

  // Safe property access
  safeAccess(obj, path, defaultValue = null) {
    return path.split(".").reduce((current, key) => {
      return current && current[key] !== undefined
        ? current[key]
        : defaultValue;
    }, obj);
  },
};

// Enhanced Analysis Module
window.SolanaAI.analysis = {
  extractTokenInfo(result) {
    return {
      name: this.extractTokenName(result),
      symbol: this.extractTokenSymbol(result),
      address: result.token_address || result.token || "N/A",
      decimals: window.SolanaAI.utils.safeAccess(result, "token_info.decimals"),
      supply: window.SolanaAI.utils.safeAccess(result, "token_info.supply"),
    };
  },

  extractTokenName(result) {
    // Try SolanaFM first
    const solanafmName = window.SolanaAI.utils.safeAccess(
      result,
      "service_responses.solanafm.token.tokenList.name"
    );
    if (solanafmName) return solanafmName;

    // Try Helius metadata
    const heliusName = window.SolanaAI.utils.safeAccess(
      result,
      "service_responses.helius.metadata.name"
    );
    if (heliusName) return heliusName;

    // Try other common paths
    const tokenInfoName =
      window.SolanaAI.utils.safeAccess(result, "token_info.name") ||
      window.SolanaAI.utils.safeAccess(result, "data.token_info.name");
    if (tokenInfoName) return tokenInfoName;

    return "Unknown Token";
  },

  extractTokenSymbol(result) {
    // Try SolanaFM first (correct path as mentioned)
    const solanafmSymbol = window.SolanaAI.utils.safeAccess(
      result,
      "service_responses.solanafm.token.tokenList.symbol"
    );
    if (solanafmSymbol) return solanafmSymbol;

    // Try Helius metadata
    const heliusSymbol = window.SolanaAI.utils.safeAccess(
      result,
      "service_responses.helius.metadata.symbol"
    );
    if (heliusSymbol) return heliusSymbol;

    // Try other common paths
    const tokenInfoSymbol =
      window.SolanaAI.utils.safeAccess(result, "token_info.symbol") ||
      window.SolanaAI.utils.safeAccess(result, "data.token_info.symbol");
    if (tokenInfoSymbol) return tokenInfoSymbol;

    return "N/A";
  },

  extractPriceData(result) {
    const price =
      window.SolanaAI.utils.safeAccess(result, "price_data") ||
      window.SolanaAI.utils.safeAccess(result, "data.price_data") ||
      {};

    return {
      current_price: price.current_price || price.value || 0,
      price_change_24h:
        price.price_change_24h || price.price24hChangePercent || 0,
      volume_24h: price.volume_24h || price.v24hUSD || 0,
      market_cap: price.market_cap || price.mc || 0,
      liquidity: price.liquidity || 0,
    };
  },

  extractQuickAnalysis(result) {
    const quick =
      window.SolanaAI.utils.safeAccess(result, "quick_analysis") ||
      window.SolanaAI.utils.safeAccess(result, "data.quick_analysis");

    if (!quick) return null;

    return {
      score: quick.score || 0,
      risk_level: quick.risk_level || "unknown",
      recommendation: quick.recommendation || "HOLD",
      key_insights: quick.key_insights || [],
      processing_time: quick.processing_time || 0,
      confidence: quick.confidence || 0,
    };
  },

  extractDeepAnalysis(result) {
    const deep =
      window.SolanaAI.utils.safeAccess(result, "deep_analysis") ||
      window.SolanaAI.utils.safeAccess(result, "data.deep_analysis");

    if (!deep) return null;

    return {
      score: deep.score || 0,
      pump_probability_1h: deep.pump_probability_1h || 0,
      pump_probability_24h: deep.pump_probability_24h || 0,
      patterns: deep.patterns || [],
      price_targets: deep.price_targets || {},
      processing_time: deep.processing_time || 0,
    };
  },

  extractSecurityAnalysis(result) {
    const security =
      window.SolanaAI.utils.safeAccess(result, "security_analysis") ||
      window.SolanaAI.utils.safeAccess(result, "data.security_analysis");

    if (!security) return null;

    return {
      overall_security_score: security.overall_security_score || 0,
      risk_factors: security.risk_factors || [],
      security_warnings: security.security_warnings || [],
    };
  },

  extractOnChainMetrics(result) {
    const metrics =
      window.SolanaAI.utils.safeAccess(result, "on_chain_metrics") ||
      window.SolanaAI.utils.safeAccess(result, "data.on_chain_metrics");

    if (!metrics) return null;

    return {
      holder_analysis: {
        holder_count: metrics.holder_analysis?.holder_count || 0,
        concentration: metrics.holder_analysis?.concentration || {},
      },
      transaction_activity: {
        "24h_transactions":
          metrics.transaction_activity?.["24h_transactions"] || 0,
        average_transaction_size:
          metrics.transaction_activity?.average_transaction_size || 0,
      },
    };
  },

  extractRiskAssessment(result) {
    const risk =
      window.SolanaAI.utils.safeAccess(result, "risk_assessment") ||
      window.SolanaAI.utils.safeAccess(result, "data.risk_assessment");

    if (!risk) return null;

    return {
      risk_category: risk.risk_category || "unknown",
      overall_risk_score: risk.overall_risk_score || 0,
      risk_factors: risk.risk_factors || [],
    };
  },

  generateAnalysisId() {
    return `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
  },

  // Extract analysis ID from the correct location (top level)
  extractAnalysisId(result) {
    // Check top level first (as mentioned by user)
    if (result.analysis_id) {
      return result.analysis_id;
    }

    // Try other common paths
    if (result.data?.analysis_id) {
      return result.data.analysis_id;
    }

    if (result.metadata?.analysis_id) {
      return result.metadata.analysis_id;
    }

    // Generate one if not found
    return this.generateAnalysisId();
  },

  // Generate human-readable summary
  generateSummary(result) {
    if (!result) return "Analysis completed";

    const tokenInfo = this.extractTokenInfo(result);
    const quickAnalysis = this.extractQuickAnalysis(result);

    let summary = `Analysis completed for ${tokenInfo.name || "token"}`;

    if (quickAnalysis) {
      const score = Math.round(quickAnalysis.score * 100);
      summary += ` (Score: ${score}%, Risk: ${quickAnalysis.risk_level})`;
    }

    return summary;
  },

  // Extract key metrics for dashboard display
  extractKeyMetrics(result) {
    const metrics = {
      score: 0,
      riskLevel: "unknown",
      recommendation: "HOLD",
      priceChange: 0,
      volume: 0,
      holders: 0,
    };

    if (!result) return metrics;

    const quick = this.extractQuickAnalysis(result);
    const price = this.extractPriceData(result);
    const onChain = this.extractOnChainMetrics(result);

    if (quick) {
      metrics.score = Math.round((quick.score || 0) * 100);
      metrics.riskLevel = quick.risk_level || "unknown";
      metrics.recommendation = quick.recommendation || "HOLD";
    }

    if (price) {
      metrics.priceChange = price.price_change_24h || 0;
      metrics.volume = price.volume_24h || 0;
    }

    if (onChain) {
      metrics.holders = onChain.holder_analysis?.holder_count || 0;
    }

    return metrics;
  },
};

// Enhanced API functions with proper error handling
window.SolanaAI.api = {
  // Base request function with improved error handling
  async request(endpoint, options = {}) {
    const url = `${window.SolanaAI.config.apiBaseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
        ...options,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message ||
            data.detail ||
            `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return data;
    } catch (error) {
      console.error(`API Error for ${endpoint}:`, error);
      throw error;
    }
  },

  // System endpoints
  async getSystemHealth() {
    return this.request("/health");
  },

  async getDashboardData() {
    return this.request("/api/dashboard");
  },

  async getApiServicesHealth() {
    return this.request("/api/health");
  },

  // New integrated analysis endpoints
  async quickAnalysis(tokenMint) {
    console.log(`🚀 Starting quick analysis for ${tokenMint}`);
    return this.request(`/quick/${tokenMint}`, {
      method: "POST",
    });
  },

  async deepAnalysis(tokenMint) {
    console.log(`🧠 Starting deep analysis for ${tokenMint}`);
    return this.request(`/deep/${tokenMint}`, {
      method: "POST",
    });
  },

  // Comprehensive token analysis using API router
  async analyzeTokenComprehensive(tokenMint, forceRefresh = false) {
    console.log(`🔍 Starting comprehensive analysis for ${tokenMint}`);
    return this.request("/api/analyze/token", {
      method: "POST",
      body: JSON.stringify({
        token_address: tokenMint,
        force_refresh: forceRefresh,
      }),
    });
  },

  // Batch analysis
  async batchAnalyzeTokens(tokenAddresses, maxConcurrent = 3) {
    console.log(
      `📊 Starting batch analysis for ${tokenAddresses.length} tokens`
    );
    return this.request("/api/analyze/batch", {
      method: "POST",
      body: JSON.stringify({
        token_addresses: tokenAddresses,
        max_concurrent: maxConcurrent,
      }),
    });
  },

  // Get analysis statistics
  async getAnalysisStats() {
    return this.request("/api/analyze/stats");
  },

  // Get services status
  async getServicesStatus() {
    return this.request("/api/services/status");
  },

  // Get recent webhook analyses
  async getRecentAnalyses(limit = 10) {
    return this.request(`/api/analyze/recent?limit=${limit}`);
  },

  // Legacy command endpoints (keeping for backward compatibility)
  async tweetCommand(tokenMint) {
    console.log(`🐦 Tweet command for ${tokenMint}`);
    return this.request(`/tweet/${tokenMint}`, { method: "POST" });
  },

  async nameCommand(tokenMint) {
    console.log(`📝 Name command for ${tokenMint}`);
    return this.request(`/name/${tokenMint}`, { method: "POST" });
  },

  async searchCommand() {
    return this.request("/search");
  },

  async whalesCommand(tokenMint = null) {
    const url = tokenMint ? `/kity+dev?token_mint=${tokenMint}` : "/kity+dev";
    return this.request(url);
  },

  async listingCommand(hours = 24) {
    return this.request(`/listing?hours=${hours}`);
  },

  // Notifications
  async getNotifications() {
    return this.request("/api/notifications");
  },

  // Helper function to choose the best analysis endpoint based on requirements
  async analyzeToken(tokenMint, analysisType = "quick", options = {}) {
    const startTime = Date.now();

    try {
      let result;

      switch (analysisType) {
        case "quick":
          result = await this.quickAnalysis(tokenMint);
          break;

        case "deep":
          result = await this.deepAnalysis(tokenMint);
          break;

        case "comprehensive":
          result = await this.analyzeTokenComprehensive(
            tokenMint,
            options.forceRefresh
          );
          break;

        case "legacy":
          // Use legacy tweet/name commands for backward compatibility
          result = await this.tweetCommand(tokenMint);
          break;

        default:
          throw new Error(`Unknown analysis type: ${analysisType}`);
      }

      // Add timing information
      const processingTime = (Date.now() - startTime) / 1000;
      if (result && typeof result === "object") {
        result.frontend_processing_time = processingTime;
      }

      console.log(`✅ Analysis completed in ${processingTime.toFixed(2)}s`);
      return result;
    } catch (error) {
      const processingTime = (Date.now() - startTime) / 1000;
      console.error(
        `❌ Analysis failed after ${processingTime.toFixed(2)}s:`,
        error
      );
      throw error;
    }
  },
};

// Enhanced notification system with better error handling
window.SolanaAI.notifications = {
  show(type, title, message, duration = 5000) {
    const notification = {
      id: window.SolanaAI.utils.generateId(),
      type,
      title,
      message,
      timestamp: Date.now(),
    };

    // Add to global state
    window.SolanaAI.state.notifications.unshift(notification);

    // Try to trigger Alpine.js update if available
    try {
      if (window.Alpine && window.Alpine.store) {
        const appStore = window.Alpine.store("app");
        if (appStore && appStore.showNotification) {
          appStore.showNotification(type, title, message);
        }
      }

      // Also try to find and update any Alpine component with notification capability
      const alpineElements = document.querySelectorAll("[x-data]");
      alpineElements.forEach((element) => {
        if (
          element.__x &&
          element.__x.$data &&
          element.__x.$data.showNotification
        ) {
          try {
            element.__x.$data.showNotification(type, title, message);
          } catch (e) {
            console.debug(
              "Could not trigger notification on Alpine component:",
              e
            );
          }
        }
      });
    } catch (error) {
      console.debug("Alpine.js notification integration failed:", error);
    }

    // Fallback: Create DOM notification if no Alpine.js component handled it
    this.createDOMNotification(notification);

    // Auto remove after duration
    if (duration > 0) {
      setTimeout(() => {
        this.remove(notification.id);
      }, duration);
    }

    return notification.id;
  },

  createDOMNotification(notification) {
    // Check if there's already a notification container
    let container = document.getElementById("notification-container");

    if (!container) {
      container = document.createElement("div");
      container.id = "notification-container";
      container.className = "fixed top-4 right-4 z-50 space-y-2";
      document.body.appendChild(container);
    }

    const notificationElement = document.createElement("div");
    notificationElement.id = `notification-${notification.id}`;
    notificationElement.className = `
      bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm
      transform transition-all duration-300 ease-in-out
      ${this.getNotificationClasses(notification.type)}
    `;

    notificationElement.innerHTML = `
      <div class="flex items-start">
        <div class="flex-shrink-0">
          <i class="${this.getNotificationIcon(
            notification.type
          )} ${this.getNotificationIconColor(notification.type)}"></i>
        </div>
        <div class="ml-3 flex-1">
          <p class="text-sm font-medium text-gray-900">${notification.title}</p>
          <p class="text-sm text-gray-600">${notification.message}</p>
        </div>
        <button class="ml-4 text-gray-400 hover:text-gray-600" onclick="window.SolanaAI.notifications.remove('${
          notification.id
        }')">
          <i class="fas fa-times"></i>
        </button>
      </div>
    `;

    // Add with animation
    notificationElement.style.transform = "translateX(100%)";
    container.appendChild(notificationElement);

    // Trigger animation
    setTimeout(() => {
      notificationElement.style.transform = "translateX(0)";
    }, 10);
  },

  getNotificationClasses(type) {
    const classes = {
      success: "border-l-4 border-green-400",
      error: "border-l-4 border-red-400",
      warning: "border-l-4 border-yellow-400",
      info: "border-l-4 border-blue-400",
    };
    return classes[type] || classes.info;
  },

  getNotificationIcon(type) {
    const icons = {
      success: "fas fa-check-circle",
      error: "fas fa-exclamation-circle",
      warning: "fas fa-exclamation-triangle",
      info: "fas fa-info-circle",
    };
    return icons[type] || icons.info;
  },

  getNotificationIconColor(type) {
    const colors = {
      success: "text-green-500",
      error: "text-red-500",
      warning: "text-yellow-500",
      info: "text-blue-500",
    };
    return colors[type] || colors.info;
  },

  remove(id) {
    // Remove from global state
    const index = window.SolanaAI.state.notifications.findIndex(
      (n) => n.id === id
    );
    if (index !== -1) {
      window.SolanaAI.state.notifications.splice(index, 1);
    }

    // Remove DOM element with animation
    const element = document.getElementById(`notification-${id}`);
    if (element) {
      element.style.transform = "translateX(100%)";
      element.style.opacity = "0";
      setTimeout(() => {
        if (element.parentNode) {
          element.parentNode.removeChild(element);
        }
      }, 300);
    }
  },

  success(title, message, duration) {
    return this.show("success", title, message, duration);
  },

  error(title, message, duration) {
    return this.show("error", title, message, duration);
  },

  warning(title, message, duration) {
    return this.show("warning", title, message, duration);
  },

  info(title, message, duration) {
    return this.show("info", title, message, duration);
  },

  // Clear all notifications
  clearAll() {
    window.SolanaAI.state.notifications.forEach((notification) => {
      this.remove(notification.id);
    });
    window.SolanaAI.state.notifications = [];
  },
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  console.log("🎯 DOM loaded, initializing Solana AI frontend...");

  // Initialize configuration
  window.SolanaAI.config.apiBaseUrl = window.location.origin;

  // Setup global error handling with better notifications
  window.addEventListener("error", function (e) {
    console.error("Global error:", e.error);

    // Don't show notifications for minor errors or Alpine.js evaluation errors
    if (
      e.error &&
      e.error.message &&
      (e.error.message.includes("Alpine Expression Error") ||
        e.error.message.includes("Cannot read properties of null"))
    ) {
      console.debug("Ignoring Alpine.js evaluation error:", e.error.message);
      return;
    }

    window.SolanaAI.notifications.error(
      "System Error",
      "An unexpected error occurred. Please refresh the page if problems persist."
    );
  });

  // Setup unhandled promise rejection handling
  window.addEventListener("unhandledrejection", function (e) {
    console.error("Unhandled promise rejection:", e.reason);

    // Don't show notifications for network errors that are already handled
    if (
      e.reason &&
      e.reason.message &&
      (e.reason.message.includes("fetch") ||
        e.reason.message.includes("NetworkError"))
    ) {
      console.debug("Network error already handled:", e.reason.message);
      return;
    }

    window.SolanaAI.notifications.error(
      "Network Error",
      "A network request failed. Please check your connection."
    );
  });

  // Initialize periodic health checks
  let healthCheckInterval = setInterval(async () => {
    try {
      const health = await window.SolanaAI.api.getSystemHealth();
      window.SolanaAI.state.systemHealth = health;
      window.SolanaAI.state.connected = health.overall_status;

      // Also check API services health
      const apiHealth = await window.SolanaAI.api.getApiServicesHealth();
      window.SolanaAI.state.apiHealth = apiHealth;
    } catch (error) {
      console.warn("Health check failed:", error);
      window.SolanaAI.state.connected = false;
    }
  }, 60000); // Check every 60 seconds (reduced frequency)

  // Initial health check
  setTimeout(async () => {
    try {
      const health = await window.SolanaAI.api.getSystemHealth();
      window.SolanaAI.state.systemHealth = health;
      window.SolanaAI.state.connected = health.overall_status;
      console.log("✅ Initial system health check completed");
    } catch (error) {
      console.warn("Initial health check failed:", error);
      window.SolanaAI.state.connected = false;
    }
  }, 1000);

  // Cleanup interval on page unload
  window.addEventListener("beforeunload", () => {
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
    }
  });

  console.log("✅ Solana AI frontend initialized successfully");
});

// Export for global access
window.SolanaAI.version = "1.0.0";
window.SolanaAI.initialized = true;

// Enhanced global functions for Alpine.js components
window.analyzeTokenGlobal = async function (tokenMint, analysisType = "quick") {
  try {
    return await window.SolanaAI.api.analyzeToken(tokenMint, analysisType);
  } catch (error) {
    console.error("Global token analysis failed:", error);
    window.SolanaAI.notifications.error(
      "Analysis Failed",
      error.message || "Failed to analyze token"
    );
    throw error;
  }
};

window.extractKeyMetricsGlobal = function (result) {
  return window.SolanaAI.analysis.extractKeyMetrics(result);
};

// Enhanced notification helpers for Alpine.js components
window.showSuccessNotification = function (title, message) {
  return window.SolanaAI.notifications.success(title, message);
};

window.showErrorNotification = function (title, message) {
  return window.SolanaAI.notifications.error(title, message);
};

window.showWarningNotification = function (title, message) {
  return window.SolanaAI.notifications.warning(title, message);
};

window.showInfoNotification = function (title, message) {
  return window.SolanaAI.notifications.info(title, message);
};

// Debug helper to check API availability
window.debugSolanaAI = function () {
  console.log("🔍 SolanaAI Debug Info:");
  console.log("- API Base URL:", window.SolanaAI.config.apiBaseUrl);
  console.log("- System State:", window.SolanaAI.state);
  console.log("- Available API methods:", Object.keys(window.SolanaAI.api));
  console.log("- Utils available:", Object.keys(window.SolanaAI.utils));
  console.log("- Analysis module:", Object.keys(window.SolanaAI.analysis));
  console.log(
    "- Notification system:",
    Object.keys(window.SolanaAI.notifications)
  );
  console.log("- Current notifications:", window.SolanaAI.state.notifications);
};

// Test notification function
window.testNotifications = function () {
  console.log("🧪 Testing notification system...");

  window.SolanaAI.notifications.success(
    "Test Success",
    "Success notification is working!"
  );

  setTimeout(() => {
    window.SolanaAI.notifications.warning(
      "Test Warning",
      "Warning notification is working!"
    );
  }, 1000);

  setTimeout(() => {
    window.SolanaAI.notifications.error(
      "Test Error",
      "Error notification is working!"
    );
  }, 2000);

  setTimeout(() => {
    window.SolanaAI.notifications.info(
      "Test Complete",
      "All notification types tested!"
    );
  }, 3000);
};

console.log("🎉 Enhanced Solana AI frontend with notification system loaded");
console.log("🔧 Use window.debugSolanaAI() to check system status");
console.log("🧪 Use window.testNotifications() to test notification system");
