// Updated main.js - Enhanced API integration for token analysis
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
  ws: null,
};

// Utility functions (keeping existing ones and adding new ones)
window.SolanaAI.utils = {
  // Format numbers with K/M/B suffixes
  formatNumber(num) {
    if (!num && num !== 0) return "N/A";
    if (num >= 1e9) return (num / 1e9).toFixed(2) + "B";
    if (num >= 1e6) return (num / 1e6).toFixed(2) + "M";
    if (num >= 1e3) return (num / 1e3).toFixed(2) + "K";
    return num.toFixed(2);
  },

  // Format percentage with + sign
  formatPercent(num) {
    if (!num && num !== 0) return "N/A";
    return `${num > 0 ? "+" : ""}${num.toFixed(2)}%`;
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
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return "Just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
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
};

// Analysis result processing utilities
window.SolanaAI.analysis = {
  // Format analysis result for display
  formatAnalysisResult(result) {
    if (!result) return null;

    return {
      success: result.success || false,
      token: result.token || result.metadata?.token_address || "Unknown",
      formattedData: {
        tokenInfo: this.extractTokenInfo(result),
        priceData: this.extractPriceData(result),
        quickAnalysis: this.extractQuickAnalysis(result),
        deepAnalysis: this.extractDeepAnalysis(result),
        securityAnalysis: this.extractSecurityAnalysis(result),
        onChainMetrics: this.extractOnChainMetrics(result),
        riskAssessment: this.extractRiskAssessment(result),
      },
      rawData: result,
      processingTime:
        result.processing_time || result.metadata?.processing_time_seconds || 0,
      timestamp: result.timestamp || new Date().toISOString(),
    };
  },

  extractTokenInfo(result) {
    if (result.token_information) {
      return {
        name: result.token_information.name || "Unknown Token",
        symbol: result.token_information.symbol || "UNK",
        mint:
          result.token_information.mint_address || result.token || "Unknown",
      };
    }
    return {
      name: "Unknown Token",
      symbol: "UNK",
      mint: result.token || "Unknown",
    };
  },

  extractPriceData(result) {
    if (result.market_data?.price_information) {
      const priceInfo = result.market_data.price_information;
      return {
        current_price: priceInfo.current_price || 0,
        price_change_24h: priceInfo.price_change_24h || 0,
        volume_24h: priceInfo.volume_24h || 0,
        market_cap: priceInfo.market_cap || 0,
      };
    }
    return {};
  },

  extractQuickAnalysis(result) {
    if (result.overall_analysis) {
      return {
        score: result.overall_analysis.score / 100 || 0,
        risk_level: result.risk_assessment?.risk_category || "unknown",
        recommendation: result.overall_analysis.recommendation || "HOLD",
        key_insights: result.overall_analysis.positive_signals || [],
        processing_time: result.metadata?.processing_time_seconds || 0,
      };
    }
    return null;
  },

  extractDeepAnalysis(result) {
    // This would be populated from deep analysis endpoint
    return null;
  },

  extractSecurityAnalysis(result) {
    if (result.security_analysis) {
      return {
        overall_security_score:
          result.security_analysis.overall_security_score || 0,
        risk_factors: result.security_analysis.risk_factors || [],
        security_checks: result.security_analysis.security_checks || {},
      };
    }
    return null;
  },

  extractOnChainMetrics(result) {
    if (result.on_chain_metrics) {
      return {
        holder_analysis: result.on_chain_metrics.holder_analysis || {},
        transaction_activity:
          result.on_chain_metrics.transaction_activity || {},
      };
    }
    return null;
  },

  extractRiskAssessment(result) {
    if (result.risk_assessment) {
      return {
        risk_category: result.risk_assessment.risk_category || "unknown",
        overall_risk_score: result.risk_assessment.overall_risk_score || 0,
        risk_factors: result.risk_assessment.risk_factors || [],
      };
    }
    return null;
  },

  // Generate summary for notifications
  generateSummary(result) {
    if (!result) return "Analysis completed";

    const score = result.overall_analysis?.score || 0;
    const risk = result.risk_assessment?.risk_category || "unknown";
    const token = result.token || result.metadata?.token_address || "token";

    return `Analysis complete: Score ${score}%, Risk: ${risk.toUpperCase()}`;
  },

  // Simple result popup
  showResultPopup(result) {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5); z-index: 9999;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    `;

    const popup = document.createElement("div");
    popup.style.cssText = `
      background: white; border-radius: 8px; padding: 20px;
      max-width: 600px; width: 100%; max-height: 80vh; overflow: auto;
    `;

    popup.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h3 style="margin: 0; font-size: 18px; font-weight: bold;">Analysis Result</h3>
        <button onclick="this.closest('.popup-overlay').remove()" style="border: none; background: none; font-size: 20px; cursor: pointer;">&times;</button>
      </div>
      <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; overflow: auto; white-space: pre-wrap; font-size: 12px;">${JSON.stringify(
        result,
        null,
        2
      )}</pre>
    `;

    overlay.className = "popup-overlay";
    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    overlay.onclick = (e) => e.target === overlay && overlay.remove();
  },

  createPopupHtml(formatted) {
    const tokenInfo = formatted.formattedData.tokenInfo;
    const quickAnalysis = formatted.formattedData.quickAnalysis;
    const priceData = formatted.formattedData.priceData;

    return `
      <div class="analysis-popup-content">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-gray-900">Analysis Results</h3>
          <button onclick="window.SolanaAI.analysis.closePopup()" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <!-- Token Info -->
        <div class="mb-4 p-3 bg-gray-50 rounded-lg">
          <h4 class="font-medium text-gray-900">${tokenInfo.name}</h4>
          <p class="text-sm text-gray-600">${tokenInfo.symbol}</p>
          <p class="text-xs text-gray-400 font-mono">${window.SolanaAI.utils.truncateAddress(
            tokenInfo.mint
          )}</p>
        </div>

        ${
          quickAnalysis
            ? `
        <!-- Analysis Score -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-gray-700">Analysis Score</span>
            <span class="text-lg font-semibold text-blue-600">${Math.round(
              quickAnalysis.score * 100
            )}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2">
            <div class="bg-blue-600 h-2 rounded-full" style="width: ${
              quickAnalysis.score * 100
            }%"></div>
          </div>
        </div>

        <!-- Risk & Recommendation -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div class="text-center p-2 bg-gray-50 rounded">
            <div class="text-xs text-gray-500">Risk Level</div>
            <div class="font-medium ${this.getRiskColorClass(
              quickAnalysis.risk_level
            )}">${quickAnalysis.risk_level.toUpperCase()}</div>
          </div>
          <div class="text-center p-2 bg-gray-50 rounded">
            <div class="text-xs text-gray-500">Recommendation</div>
            <div class="font-medium ${this.getRecommendationColorClass(
              quickAnalysis.recommendation
            )}">${quickAnalysis.recommendation}</div>
          </div>
        </div>
        `
            : ""
        }

        ${
          priceData.current_price
            ? `
        <!-- Price Data -->
        <div class="mb-4">
          <h5 class="text-sm font-medium text-gray-700 mb-2">Market Data</h5>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>Price: $${window.SolanaAI.utils.formatCurrency(
              priceData.current_price
            )}</div>
            <div class="${
              priceData.price_change_24h >= 0
                ? "text-green-600"
                : "text-red-600"
            }">
              24h: ${window.SolanaAI.utils.formatPercent(
                priceData.price_change_24h
              )}
            </div>
          </div>
        </div>
        `
            : ""
        }

        ${
          quickAnalysis?.key_insights?.length
            ? `
        <!-- Key Insights -->
        <div class="mb-4">
          <h5 class="text-sm font-medium text-gray-700 mb-2">Key Insights</h5>
          <ul class="space-y-1">
            ${quickAnalysis.key_insights
              .slice(0, 3)
              .map(
                (insight) => `
              <li class="text-sm text-gray-600 flex items-start">
                <i class="fas fa-chevron-right text-blue-500 mr-2 mt-0.5 text-xs"></i>
                <span>${insight}</span>
              </li>
            `
              )
              .join("")}
          </ul>
        </div>
        `
            : ""
        }

        <!-- Actions -->
        <div class="flex space-x-3 pt-3 border-t">
          <button 
            onclick="window.location.href='/analysis?token=${tokenInfo.mint}'" 
            class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm"
          >
            View Full Analysis
          </button>
          <button 
            onclick="window.SolanaAI.analysis.closePopup()" 
            class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
          >
            Close
          </button>
        </div>

        <!-- Processing Time -->
        <div class="mt-3 text-xs text-gray-500 text-center">
          Processed in ${formatted.processingTime.toFixed(2)}s
        </div>
      </div>
    `;
  },

  createAndShowPopup(htmlContent) {
    console.log("🚀 createAndShowPopup called");

    // Remove existing popup
    const existingPopup = document.querySelector(".analysis-popup-overlay");
    if (existingPopup) {
      console.log("Removing existing popup");
      existingPopup.remove();
    }

    // Create popup overlay
    const overlay = document.createElement("div");
    overlay.className = "analysis-popup-overlay";
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-color: rgba(0, 0, 0, 0.5);
      z-index: 9999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    `;

    // Create popup container
    const popup = document.createElement("div");
    popup.className = "analysis-popup";
    popup.style.cssText = `
      background: white;
      border-radius: 0.75rem;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
      max-width: 28rem;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      padding: 1.5rem;
    `;
    popup.innerHTML = htmlContent;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    console.log("✅ Popup added to DOM");

    // Close on overlay click
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        console.log("Closing popup via overlay click");
        this.closePopup();
      }
    });

    // Close on escape
    const handleEscape = (e) => {
      if (e.key === "Escape") {
        console.log("Closing popup via escape key");
        this.closePopup();
        document.removeEventListener("keydown", handleEscape);
      }
    };
    document.addEventListener("keydown", handleEscape);
  },

  closePopup() {
    console.log("🚀 closePopup called");
    const popup = document.querySelector(".analysis-popup-overlay");
    if (popup) {
      console.log("✅ Removing popup from DOM");
      popup.remove();
    } else {
      console.log("❌ No popup found to remove");
    }
  },

  getRiskColorClass(risk) {
    const colorMap = {
      low: "text-green-600",
      medium: "text-yellow-600",
      high: "text-red-600",
      critical: "text-red-800",
    };
    return colorMap[risk?.toLowerCase()] || "text-gray-600";
  },

  getRecommendationColorClass(recommendation) {
    const colorMap = {
      BUY: "text-green-600",
      CONSIDER: "text-blue-600",
      HOLD: "text-yellow-600",
      CAUTION: "text-orange-600",
      AVOID: "text-red-600",
    };
    return colorMap[recommendation] || "text-gray-600";
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

    const result = await this.request(`/quick/${tokenMint}`, {
      method: "POST",
    });

    // Show popup with raw result
    this.showResultPopup(result);

    return result;
  },

  // Simple result popup
  showResultPopup(result) {
    const overlay = document.createElement("div");
    overlay.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5); z-index: 9999;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    `;

    const popup = document.createElement("div");
    popup.style.cssText = `
      background: white; border-radius: 8px; padding: 20px;
      max-width: 600px; width: 100%; max-height: 80vh; overflow: auto;
    `;

    popup.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h3 style="margin: 0; font-size: 18px; font-weight: bold;">Analysis Result</h3>
        <button onclick="this.closest('.popup-overlay').remove()" style="border: none; background: none; font-size: 20px; cursor: pointer;">&times;</button>
      </div>
      <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; overflow: auto; white-space: pre-wrap; font-size: 12px;">${JSON.stringify(
        result,
        null,
        2
      )}</pre>
    `;

    overlay.className = "popup-overlay";
    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    overlay.onclick = (e) => e.target === overlay && overlay.remove();
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

// Enhanced notification system
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

    // Trigger Alpine.js update if available
    if (window.Alpine && window.Alpine.store) {
      const appStore = window.Alpine.store("app");
      if (appStore) {
        appStore.showNotification(type, title, message);
      }
    }

    // Auto remove after duration
    if (duration > 0) {
      setTimeout(() => {
        this.remove(notification.id);
      }, duration);
    }

    return notification.id;
  },

  remove(id) {
    const index = window.SolanaAI.state.notifications.findIndex(
      (n) => n.id === id
    );
    if (index !== -1) {
      window.SolanaAI.state.notifications.splice(index, 1);
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
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  console.log("🎯 DOM loaded, initializing Solana AI frontend...");

  // Initialize configuration
  window.SolanaAI.config.apiBaseUrl = window.location.origin;

  // Setup global error handling
  window.addEventListener("error", function (e) {
    console.error("Global error:", e.error);
    window.SolanaAI.notifications.error(
      "System Error",
      "An unexpected error occurred. Please refresh the page if problems persist."
    );
  });

  // Setup unhandled promise rejection handling
  window.addEventListener("unhandledrejection", function (e) {
    console.error("Unhandled promise rejection:", e.reason);
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
  }, 30000); // Check every 30 seconds

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
    throw error;
  }
};

// Debug helper to check API availability
window.debugSolanaAI = function () {
  console.log("🔍 SolanaAI Debug Info:");
  console.log("- API Base URL:", window.SolanaAI.config.apiBaseUrl);
  console.log("- System State:", window.SolanaAI.state);
  console.log("- Available API methods:", Object.keys(window.SolanaAI.api));
  console.log("- Utils available:", Object.keys(window.SolanaAI.utils));
};

// Add popup styles to document
const popupStyles = `
.analysis-popup-overlay {
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease-out;
}

.analysis-popup {
  animation: slideInUp 0.3s ease-out;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideInUp {
  from { 
    opacity: 0;
    transform: translateY(20px);
  }
  to { 
    opacity: 1;
    transform: translateY(0);
  }
}

.analysis-popup-content {
  max-height: 80vh;
  overflow-y: auto;
}

.analysis-popup-content::-webkit-scrollbar {
  width: 4px;
}

.analysis-popup-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 2px;
}

.analysis-popup-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 2px;
}

.analysis-popup-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
`;

// Inject styles
if (!document.querySelector("#analysis-popup-styles")) {
  const styleSheet = document.createElement("style");
  styleSheet.id = "analysis-popup-styles";
  styleSheet.textContent = popupStyles;
  document.head.appendChild(styleSheet);
}

console.log("🎉 Enhanced Solana AI frontend API integration loaded");
console.log("🔧 Use window.debugSolanaAI() to check system status");
