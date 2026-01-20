/**
 * PM2 Ecosystem Configuration
 * OnChain Intelligence API
 * 
 * Usage:
 *   pm2 start ecosystem.config.js
 *   pm2 stop all
 *   pm2 restart all
 *   pm2 logs
 * 
 * Note: Environment variables are loaded from .env by the Python app itself.
 * We don't use dotenv here to avoid Node.js module dependency.
 */

// Read env vars directly (set them in shell or use: source .env && pm2 start ...)
const APP_NAME = process.env.PM2_APP_NAME || 'onchain-intelligence';
const PORT = process.env.ONCHAIN_API_PORT || 8500;
const INSTANCES = process.env.PM2_INSTANCES || 1;
const MAX_MEMORY = process.env.PM2_MAX_MEMORY || '512M';
const LOG_LEVEL = process.env.ONCHAIN_LOG_LEVEL || 'INFO';

// Detect Python interpreter path (Linux: venv/bin/python, Windows: .venv/Scripts/python.exe)
const fs = require('fs');
const path = require('path');
let PYTHON_INTERPRETER = 'python3';  // fallback

// Check for Linux venv first
if (fs.existsSync(path.join(__dirname, 'venv', 'bin', 'python'))) {
  PYTHON_INTERPRETER = path.join(__dirname, 'venv', 'bin', 'python');
} 
// Check for Windows .venv
else if (fs.existsSync(path.join(__dirname, '.venv', 'Scripts', 'python.exe'))) {
  PYTHON_INTERPRETER = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
}
// Check for Linux .venv
else if (fs.existsSync(path.join(__dirname, '.venv', 'bin', 'python'))) {
  PYTHON_INTERPRETER = path.join(__dirname, '.venv', 'bin', 'python');
}

module.exports = {
  apps: [
    // Main API Server
    {
      name: APP_NAME,
      script: 'api_server.py',
      interpreter: PYTHON_INTERPRETER,
      cwd: __dirname,
      
      // Process settings
      instances: parseInt(INSTANCES),
      exec_mode: 'fork',  // Use 'cluster' for Node.js only
      
      // Environment
      env: {
        NODE_ENV: 'production',
        ONCHAIN_API_PORT: PORT,
        ONCHAIN_LOG_LEVEL: LOG_LEVEL
      },
      
      // Restart settings
      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: '10s',
      restart_delay: 5000,
      
      // Memory management
      max_memory_restart: MAX_MEMORY,
      
      // Logs
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: 'logs/api-error.log',
      out_file: 'logs/api-out.log',
      merge_logs: true,
      
      // Graceful shutdown
      kill_timeout: 5000,
      listen_timeout: 10000,
      
      // Health check
      wait_ready: true,
      
      // Don't watch these
      ignore_watch: [
        'node_modules',
        'logs',
        '.git',
        '__pycache__',
        '*.pyc',
        '.venv'
      ]
    },
    
    // Background Scheduler (Optional)
    {
      name: `${APP_NAME}-scheduler`,
      script: 'scheduler.py',
      interpreter: '.venv/bin/python',
      cwd: __dirname,
      
      // Single instance only
      instances: 1,
      exec_mode: 'fork',
      
      // Environment
      env: {
        NODE_ENV: 'production',
        ONCHAIN_LOG_LEVEL: LOG_LEVEL
      },
      
      // Restart settings
      autorestart: true,
      watch: false,
      max_restarts: 5,
      min_uptime: '30s',
      restart_delay: 10000,
      
      // Memory
      max_memory_restart: '256M',
      
      // Logs
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      error_file: 'logs/scheduler-error.log',
      out_file: 'logs/scheduler-out.log',
      merge_logs: true,
      
      // Graceful shutdown
      kill_timeout: 10000
    }
  ],
  
  // Deployment configuration (for pm2 deploy)
  deploy: {
    production: {
      // SSH settings - configure in your environment
      user: process.env.DEPLOY_USER || 'deploy',
      host: process.env.DEPLOY_HOST || 'your-vps-ip',
      ref: 'origin/main',
      repo: process.env.DEPLOY_REPO || 'git@github.com:yourusername/onchain-intelligence.git',
      path: process.env.DEPLOY_PATH || '/var/www/onchain-intelligence',
      
      // Pre-deploy
      'pre-deploy-local': '',
      
      // Post-deploy
      'post-deploy': 
        'source .venv/bin/activate && ' +
        'pip install -r requirements.txt && ' +
        'pm2 reload ecosystem.config.js --env production',
      
      // Environment
      env: {
        NODE_ENV: 'production'
      }
    }
  }
};
