/**
 * PM2 configuration file for the DCR UI application.
 *
 * To use this file:
 * 1. Make sure you have PM2 installed: `npm install pm2 -g`
 * 2. From your project root, run: `pm2 start ecosystem.config.js`
 *
 * To see logs: `pm2 logs DCR-UI`
 * To stop: `pm2 stop DCR-UI`
 * To restart: `pm2 restart DCR-UI`
 */
module.exports = {
  apps: [{
    name: 'DCR-UI',
    script: './serve.py',
    interpreter: 'python' // Or 'python3' depending on your environment
  }]
};