// Main JavaScript file for Solana Token Analysis AI
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

// Utility functions
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
};

// API functions
window.SolanaAI.api = {
  // Base request function
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

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
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

  async getSystemStatus() {
    return this.request("/api/system/status");
  },

  // Analysis endpoints
  async quickAnalysis(tokenMint) {
    return this.request("/api/analysis/quick", {
      method: "POST",
      body: JSON.stringify({ token_mint: tokenMint }),
    });
  },

  async deepAnalysis(tokenMint) {
    return this.request("/api/analysis/deep", {
      method: "POST",
      body: JSON.stringify({ token_mint: tokenMint }),
    });
  },

  // Command endpoints
  async tweetCommand(tokenMint) {
    return this.request(`/tweet/${tokenMint}`, { method: "POST" });
  },

  async nameCommand(tokenMint) {
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
};

// Notification system
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
  setInterval(async () => {
    try {
      const health = await window.SolanaAI.api.getSystemStatus();
      window.SolanaAI.state.systemHealth = health;
      window.SolanaAI.state.connected = health.overall_healthy;
    } catch (error) {
      console.warn("Health check failed:", error);
      window.SolanaAI.state.connected = false;
    }
  }, 30000); // Check every 30 seconds

  console.log("✅ Solana AI frontend initialized successfully");
});

// Export for global access
window.SolanaAI.version = "1.0.0";
window.SolanaAI.initialized = true;
