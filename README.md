# FTP Pullzone Telegram Bot

A Telegram bot hosted on Replit that manages FTP file operations with automatic file replacement functionality. Designed to run 24/7 with keep-alive support.

## Features

- 🔐 Secure FTP connection with TLS support
- 📤 Upload text files with automatic renaming to `pullzone_hostnames.txt`
- 🗑️ Automatic deletion of old files before uploading new ones
- 💾 Save multiple FTP configurations per user
- ✅ Connection status checking
- 🌐 Built-in Flask server for Replit keep-alive

## Setup Instructions

### 1. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Copy the bot token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Deploy to Replit

1. Go to [Replit](https://replit.com)
2. Create a new Repl
3. Import this repository or upload the files
4. Go to the **Secrets** tab (Tools → Secrets or the lock icon 🔒)
5. Add a new secret:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: Your bot token from BotFather

### 3. Run the Bot

1. Click the **Run** button in Replit
2. The bot will start and show "Bot started successfully!"
3. A Flask server will run on port 8080 to keep the bot alive

### 4. Keep Bot Running 24/7

To keep your bot running 24/7 on Replit:

**Option 1: UptimeRobot (Recommended - Free)**
1. Sign up at [UptimeRobot](https://uptimerobot.com)
2. Create a new monitor:
   - Monitor Type: HTTP(s)
   - URL: Your Replit URL (e.g., `https://your-repl-name.your-username.repl.co`)
   - Monitoring Interval: 5 minutes
3. This will ping your bot every 5 minutes to keep it awake

**Option 2: Replit Always On (Paid)**
- Enable "Always On" in your Repl settings
- This is a paid feature but more reliable

## Bot Commands

### `/start`
Start the bot and see available commands.

### `/setup`
Configure FTP credentials step-by-step:
- FTP Host (e.g., `103.194.228.117`)
- FTP Port (e.g., `21`)
- FTP Username
- FTP Password
- FTP Path (e.g., `/public_html/v1/pullzoneurls`)

### `/upload`
Upload a text file to FTP:
1. Run `/upload`
2. Send any text file as a document
3. The bot will:
   - Delete the old `pullzone_hostnames.txt` if it exists
   - Rename your file to `pullzone_hostnames.txt`
   - Upload it to the configured FTP path

### `/status`
Check if the FTP connection is working and view connection details.

### `/help`
Display help information and usage instructions.

## Usage Example

```
You: /setup
Bot: Let's setup your FTP credentials. Please enter the FTP Host:

You: 103.194.228.117
Bot: ✅ FTP Host saved. Now enter the FTP Port:

You: 21
Bot: ✅ FTP Port saved. Now enter your FTP Username:

You: your_username
Bot: ✅ FTP Username saved. Now enter your FTP Password:

You: your_password
Bot: ✅ FTP Password saved. Now enter the FTP Path:

You: /public_html/v1/pullzoneurls
Bot: ✅ FTP Configuration Saved!

You: /upload
Bot: Please send the text file you want to upload...

You: [Send file]
Bot: ⬇️ Downloading file...
     🔄 Connecting to FTP server...
     📂 Navigating to /public_html/v1/pullzoneurls...
     🗑️ Deleting old pullzone_hostnames.txt...
     ✅ Old file deleted successfully!
     📤 Uploading as pullzone_hostnames.txt...
     ✅ Upload Successful!
```

## Technical Details

### FTP Configuration
- Supports **FTP with TLS** (FTPS) for secure connections
- Configurations are stored per-user in `ftp_config.json`
- Each user can have their own FTP credentials

### File Operations
1. When a file is uploaded:
   - Downloads the file from Telegram to a temporary location
   - Connects to FTP server with TLS
   - Navigates to the specified directory
   - Checks if `pullzone_hostnames.txt` exists
   - Deletes the old file if found
   - Uploads the new file as `pullzone_hostnames.txt`
   - Cleans up temporary files

### Keep-Alive Mechanism
- Runs a Flask web server on port 8080
- Replit keeps the bot alive as long as the web server receives requests
- Use UptimeRobot or similar service to ping the web endpoint every 5 minutes

## Project Structure

```
ftppullzonebot/
├── main.py              # Main bot code
├── requirements.txt     # Python dependencies
├── ftp_config.json     # User FTP configurations (auto-generated)
├── .replit             # Replit configuration
├── replit.nix          # Nix dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Dependencies

- `python-telegram-bot==20.7` - Telegram Bot API wrapper
- `flask==3.0.0` - Web server for keep-alive

## Security Notes

- Store your bot token in Replit Secrets, never commit it to Git
- FTP credentials are stored in `ftp_config.json` - keep this file secure
- The bot uses TLS for secure FTP connections
- Each user's FTP configuration is isolated

## Troubleshooting

### Bot not responding
- Check if the bot is running in Replit
- Verify the `TELEGRAM_BOT_TOKEN` is set correctly in Secrets
- Check the Replit console for error messages

### FTP connection failed
- Verify your FTP credentials using `/status`
- Ensure the FTP server supports TLS (FTPS)
- Check if the FTP path is correct and accessible
- Make sure port 21 is not blocked

### File upload failed
- Ensure the file is sent as a document, not as text
- Check if you have write permissions on the FTP server
- Verify the target directory exists

### Bot keeps sleeping (Replit)
- Set up UptimeRobot to ping your Repl URL every 5 minutes
- Or upgrade to Replit's "Always On" feature

## License

MIT License - feel free to modify and use as needed!

## Support

For issues or questions, check the Replit console logs for detailed error messages.
