module.exports = {
  apps: [
    {
      name: 'onchain-intel-api',
      script: 'uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000 --workers 4',
      cwd: '/path/to/onchain_intel_product',
      interpreter: 'python3',
      
      // Environment variables
      env: {
        NODE_ENV: 'production',
        ONCHAIN_LOG_LEVEL: 'INFO',
        ONCHAIN_API_HOST: '0.0.0.0',
        ONCHAIN_API_PORT: '8000',
        ONCHAIN_API_WORKERS: '4'
      },
      
      // Production environment
      env_production: {
        NODE_ENV: 'production',
        ONCHAIN_LOG_LEVEL: 'WARNING',
        ONCHAIN_API_WORKERS: '8'
      },
      
      // Process management
      instances: 1,
      exec_mode: 'fork',
      
      // Auto restart
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      
      // Logging
      log_file: './logs/onchain-intel-combined.log',
      out_file: './logs/onchain-intel-out.log',
      error_file: './logs/onchain-intel-error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // Health monitoring
      min_uptime: '10s',
      max_restarts: 10,
      
      // Graceful shutdown
      kill_timeout: 5000,
      listen_timeout: 3000,
      
      // Source maps and debugging
      source_map_support: false,
      
      // Merge logs
      merge_logs: true,
      
      // Time zone
      time: true
    }
  ],
  
  deploy: {
    production: {
      user: 'deploy',
      host: ['your-server.com'],
      ref: 'origin/main',
      repo: 'git@github.com:your-repo/onchain-intel.git',
      path: '/var/www/onchain-intel',
      'post-deploy': 'pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production',
      env: {
        NODE_ENV: 'production'
      }
    }
  }
};