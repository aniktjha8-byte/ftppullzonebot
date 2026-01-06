import os
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from ftplib import FTP_TLS, error_perm
import tempfile
from threading import Thread
from flask import Flask
import json
import traceback

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

FTP_HOST, FTP_PORT, FTP_USER, FTP_PASS, FTP_PATH = range(5)
UPLOAD_FILE = 1

FTP_CONFIG_FILE = 'ftp_config.json'

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def load_ftp_config(user_id):
    if not os.path.exists(FTP_CONFIG_FILE):
        return None
    
    try:
        with open(FTP_CONFIG_FILE, 'r') as f:
            configs = json.load(f)
            return configs.get(str(user_id))
    except Exception as e:
        logger.error(f"Error loading FTP config: {e}")
        return None

def save_ftp_config(user_id, config):
    configs = {}
    if os.path.exists(FTP_CONFIG_FILE):
        try:
            with open(FTP_CONFIG_FILE, 'r') as f:
                configs = json.load(f)
        except Exception as e:
            logger.error(f"Error reading existing config: {e}")
            pass
    
    configs[str(user_id)] = config
    
    try:
        with open(FTP_CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=2)
        logger.info(f"FTP config saved for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving FTP config: {e}")
        raise

def get_main_menu_keyboard(has_config=False):
    keyboard = [
        [InlineKeyboardButton("⚙️ Setup FTP" if not has_config else "⚙️ Edit FTP Config", callback_data="menu_setup")],
        [InlineKeyboardButton("📤 Upload File", callback_data="menu_upload")],
        [InlineKeyboardButton("✅ Test Connection", callback_data="menu_status")]
    ]
    if has_config:
        keyboard.append([InlineKeyboardButton("📋 View Saved Config", callback_data="menu_view_config")])
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="menu_help")])
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_main")]]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]]
    return InlineKeyboardMarkup(keyboard)

def clean_url_line(line):
    """
    Clean a line by removing http://, https://, www., and trailing paths/slashes.
    Returns just the hostname.
    """
    line = line.strip()
    if not line:
        return line
    
    line = re.sub(r'^https?://', '', line, flags=re.IGNORECASE)
    line = re.sub(r'^www\.', '', line, flags=re.IGNORECASE)
    line = re.sub(r'/.*$', '', line)
    line = line.strip()
    
    return line

def process_file_content(input_path, output_path):
    """
    Process file to clean URLs - remove http://, https://, www., and paths.
    Returns tuple: (lines_processed, lines_cleaned)
    """
    lines_processed = 0
    lines_cleaned = 0
    
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile:
            with open(output_path, 'w', encoding='utf-8') as outfile:
                for line in infile:
                    lines_processed += 1
                    original = line.strip()
                    cleaned = clean_url_line(original)
                    
                    if cleaned and cleaned != original:
                        lines_cleaned += 1
                    
                    if cleaned:
                        outfile.write(cleaned + '\n')
        
        return lines_processed, lines_cleaned
    except Exception as e:
        logger.error(f"Error processing file content: {e}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    config = load_ftp_config(user.id)
    
    if config:
        status_text = "✅ <b>Configured & Saved</b> (Permanent)"
        info_text = "Your FTP credentials are saved and ready to use!"
    else:
        status_text = "❌ Not configured"
        info_text = "Setup your FTP credentials once - they'll be saved permanently!"
    
    welcome_text = (
        f"👋 Hello {user.mention_html()}!\n\n"
        f"🤖 <b>FTP Pullzone Bot</b>\n\n"
        f"FTP Status: {status_text}\n"
        f"{info_text}\n\n"
        f"Select an option below:"
    )
    
    try:
        await update.message.reply_text(
            welcome_text,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard(has_config=bool(config))
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again."
        )

async def show_help(query_or_update, is_callback=False):
    help_text = (
        "📖 <b>How to use FTP Pullzone Bot:</b>\n\n"
        "<b>1️⃣ Setup FTP:</b>\n"
        "Configure your FTP server credentials (host, port, username, password, and path)\n\n"
        "<b>2️⃣ Upload File:</b>\n"
        "Send any text file and the bot will:\n"
        "   • Delete old pullzone_hostnames.txt\n"
        "   • Rename your file to pullzone_hostnames.txt\n"
        "   • Upload to your FTP server\n\n"
        "<b>3️⃣ Test Connection:</b>\n"
        "Verify your FTP credentials are working\n\n"
        "<b>🔒 Security:</b>\n"
        "All connections use TLS encryption for security."
    )
    
    try:
        if is_callback:
            await query_or_update.edit_message_text(
                help_text,
                parse_mode='HTML',
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await query_or_update.message.reply_text(
                help_text,
                parse_mode='HTML',
                reply_markup=get_back_to_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Error showing help: {e}")

async def setup_start(query_or_update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    text = (
        "🔧 <b>FTP Configuration Setup</b>\n\n"
        "Please enter the <b>FTP Host</b>\n"
        "Example: 103.194.228.117"
    )
    
    try:
        if is_callback:
            await query_or_update.edit_message_text(
                text,
                parse_mode='HTML',
                reply_markup=get_cancel_keyboard()
            )
        else:
            await query_or_update.message.reply_text(
                text,
                parse_mode='HTML',
                reply_markup=get_cancel_keyboard()
            )
        return FTP_HOST
    except Exception as e:
        logger.error(f"Error in setup_start: {e}")
        return ConversationHandler.END

async def ftp_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        host = update.message.text.strip()
        if not host or ' ' in host:
            await update.message.reply_text(
                "❌ Invalid host. Please enter a valid hostname or IP address:",
                reply_markup=get_cancel_keyboard()
            )
            return FTP_HOST
        
        context.user_data['ftp_host'] = host
        await update.message.reply_text(
            "✅ FTP Host saved\n\n"
            "Now enter the <b>FTP Port</b>\n"
            "Usually: 21",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return FTP_PORT
    except Exception as e:
        logger.error(f"Error in ftp_host: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel"
        )
        return FTP_HOST

async def ftp_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        port = int(update.message.text.strip())
        if port < 1 or port > 65535:
            await update.message.reply_text(
                "❌ Port must be between 1 and 65535. Please try again:",
                reply_markup=get_cancel_keyboard()
            )
            return FTP_PORT
        
        context.user_data['ftp_port'] = port
        await update.message.reply_text(
            "✅ FTP Port saved\n\n"
            "Now enter your <b>FTP Username</b>:",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return FTP_USER
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid port number. Please enter a valid number:",
            reply_markup=get_cancel_keyboard()
        )
        return FTP_PORT
    except Exception as e:
        logger.error(f"Error in ftp_port: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel"
        )
        return FTP_PORT

async def ftp_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        username = update.message.text.strip()
        if not username:
            await update.message.reply_text(
                "❌ Username cannot be empty. Please try again:",
                reply_markup=get_cancel_keyboard()
            )
            return FTP_USER
        
        context.user_data['ftp_user'] = username
        await update.message.reply_text(
            "✅ FTP Username saved\n\n"
            "Now enter your <b>FTP Password</b>:",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return FTP_PASS
    except Exception as e:
        logger.error(f"Error in ftp_user: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel"
        )
        return FTP_USER

async def ftp_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        password = update.message.text
        if not password:
            await update.message.reply_text(
                "❌ Password cannot be empty. Please try again:",
                reply_markup=get_cancel_keyboard()
            )
            return FTP_PASS
        
        context.user_data['ftp_pass'] = password
        
        try:
            await update.message.delete()
        except:
            pass
        
        await update.message.reply_text(
            "✅ FTP Password saved (message deleted for security)\n\n"
            "Now enter the <b>FTP Path</b>\n"
            "Example: /public_html/v1/pullzoneurls",
            parse_mode='HTML',
            reply_markup=get_cancel_keyboard()
        )
        return FTP_PATH
    except Exception as e:
        logger.error(f"Error in ftp_pass: {e}")
        await update.message.reply_text(
            "❌ An error occurred. Please try again or /cancel"
        )
        return FTP_PASS

async def ftp_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        path = update.message.text.strip()
        if not path:
            await update.message.reply_text(
                "❌ Path cannot be empty. Please try again:",
                reply_markup=get_cancel_keyboard()
            )
            return FTP_PATH
        
        context.user_data['ftp_path'] = path
        
        user_id = update.effective_user.id
        config = {
            'host': context.user_data['ftp_host'],
            'port': context.user_data['ftp_port'],
            'user': context.user_data['ftp_user'],
            'pass': context.user_data['ftp_pass'],
            'path': context.user_data['ftp_path']
        }
        
        await update.message.reply_text("💾 Saving configuration...")
        
        try:
            save_ftp_config(user_id, config)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            await update.message.reply_text(
                f"❌ Failed to save configuration: {str(e)}\n\n"
                "Please try setup again with /setup"
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            "✅ <b>FTP Configuration Saved Permanently!</b>\n\n"
            f"📡 Host: <code>{config['host']}:{config['port']}</code>\n"
            f"👤 User: <code>{config['user']}</code>\n"
            f"📂 Path: <code>{config['path']}</code>\n\n"
            f"💾 <b>Your credentials are saved in: ftp_config.json</b>\n"
            f"✨ You won't need to setup again - use /start to upload anytime!",
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
        
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in ftp_path: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ An unexpected error occurred: {str(e)}\n\n"
            "Please try again or contact support."
        )
        return ConversationHandler.END

async def setup_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "❌ FTP setup cancelled.",
            reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in setup_cancel: {e}")
    return ConversationHandler.END

async def test_connection(query_or_update, user_id, is_callback=False):
    config = load_ftp_config(user_id)
    
    if not config:
        error_msg = (
            "❌ <b>No FTP Configuration Found</b>\n\n"
            "Please setup your FTP credentials first."
        )
        try:
            if is_callback:
                await query_or_update.edit_message_text(
                    error_msg,
                    parse_mode='HTML',
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await query_or_update.message.reply_text(
                    error_msg,
                    parse_mode='HTML',
                    reply_markup=get_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Error showing no config message: {e}")
        return
    
    status_msg = "🔄 <b>Testing FTP Connection...</b>"
    try:
        if is_callback:
            await query_or_update.edit_message_text(
                status_msg,
                parse_mode='HTML'
            )
            message = query_or_update.message
        else:
            message = await query_or_update.message.reply_text(
                status_msg,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Error sending status message: {e}")
        return
    
    ftp = None
    try:
        ftp = FTP_TLS(timeout=30)
        ftp.connect(config['host'], config['port'])
        ftp.login(config['user'], config['pass'])
        ftp.prot_p()
        ftp.cwd(config['path'])
        
        files = []
        ftp.retrlines('LIST', files.append)
        
        pullzone_exists = any('pullzone_hostnames.txt' in f for f in files)
        
        success_msg = (
            f"✅ <b>Connection Successful!</b>\n\n"
            f"📡 Host: <code>{config['host']}:{config['port']}</code>\n"
            f"📂 Path: <code>{config['path']}</code>\n"
            f"📄 Files in directory: {len(files)}\n"
            f"🎯 pullzone_hostnames.txt: {'✅ Found' if pullzone_exists else '❌ Not found'}"
        )
        
        await message.edit_text(
            success_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except error_perm as e:
        error_code = str(e).split()[0] if str(e) else "Unknown"
        error_msg = (
            f"❌ <b>FTP Permission Error</b>\n\n"
            f"Code: {error_code}\n"
            f"Details: {str(e)}\n\n"
            f"Please check your credentials and permissions."
        )
        await message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    except TimeoutError:
        error_msg = (
            f"❌ <b>Connection Timeout</b>\n\n"
            f"Could not connect to {config['host']}:{config['port']}\n\n"
            f"Please check:\n"
            f"• Host is correct\n"
            f"• Port is correct\n"
            f"• Server is online"
        )
        await message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"FTP test connection error: {e}\n{traceback.format_exc()}")
        error_msg = (
            f"❌ <b>Connection Failed</b>\n\n"
            f"Error: <code>{str(e)}</code>\n\n"
            f"Please verify your FTP credentials."
        )
        await message.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    finally:
        if ftp:
            try:
                ftp.quit()
            except:
                try:
                    ftp.close()
                except:
                    pass

async def upload_start(query_or_update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    user_id = query_or_update.from_user.id if is_callback else query_or_update.effective_user.id
    config = load_ftp_config(user_id)
    
    if not config:
        error_msg = (
            "❌ <b>No FTP Configuration Found</b>\n\n"
            "Please setup your FTP credentials first."
        )
        try:
            if is_callback:
                await query_or_update.edit_message_text(
                    error_msg,
                    parse_mode='HTML',
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await query_or_update.message.reply_text(
                    error_msg,
                    parse_mode='HTML',
                    reply_markup=get_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Error showing no config message: {e}")
        return ConversationHandler.END
    
    upload_msg = (
        "📤 <b>Upload File to FTP</b>\n\n"
        "Send any text file (any filename is OK!)\n\n"
        "📝 <b>What happens:</b>\n"
        "   1️⃣ Clean URLs (remove http/https)\n"
        "   2️⃣ Upload with original name\n"
        "   3️⃣ Delete old <code>pullzone_hostnames.txt</code>\n"
        "   4️⃣ Rename to <code>pullzone_hostnames.txt</code>\n"
        "   5️⃣ Clean up temp files\n\n"
        "✨ <b>Auto-cleanup:</b> URLs are cleaned automatically!\n"
        f"📂 <b>Location:</b> <code>{config['path']}</code>\n\n"
        "Send /cancel to abort."
    )
    
    try:
        if is_callback:
            await query_or_update.edit_message_text(
                upload_msg,
                parse_mode='HTML'
            )
        else:
            await query_or_update.message.reply_text(
                upload_msg,
                parse_mode='HTML'
            )
        return UPLOAD_FILE
    except Exception as e:
        logger.error(f"Error in upload_start: {e}")
        return ConversationHandler.END

async def upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = load_ftp_config(user_id)
    
    if not config:
        await update.message.reply_text(
            "❌ FTP not configured. Setup cancelled.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return ConversationHandler.END
    
    if not update.message.document:
        await update.message.reply_text(
            "❌ Please send a file as a document, not as text.\n\n"
            "Tap the 📎 attachment icon and select your file."
        )
        return UPLOAD_FILE
    
    document = update.message.document
    file_size_mb = document.file_size / (1024 * 1024) if document.file_size else 0
    file_size_bytes = document.file_size if document.file_size else 0
    
    if file_size_mb > 20:
        await update.message.reply_text(
            f"❌ File too large ({file_size_mb:.2f} MB)\n\n"
            f"Maximum file size is 20 MB."
        )
        return UPLOAD_FILE
    
    status_msg = await update.message.reply_text("⬇️ <b>Downloading file...</b>", parse_mode='HTML')
    
    tmp_path = None
    ftp = None
    temp_upload_name = None
    
    try:
        file = await context.bot.get_file(document.file_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_file:
            await file.download_to_drive(tmp_file.name)
            tmp_path = tmp_file.name
        
        await status_msg.edit_text(
            "📦 <b>File downloaded</b>\n"
            "🧹 Processing & cleaning URLs...",
            parse_mode='HTML'
        )
        
        cleaned_tmp_path = tmp_path + '.cleaned'
        try:
            lines_processed, lines_cleaned = process_file_content(tmp_path, cleaned_tmp_path)
            logger.info(f"Processed {lines_processed} lines, cleaned {lines_cleaned} URLs")
            
            os.unlink(tmp_path)
            tmp_path = cleaned_tmp_path
            
            await status_msg.edit_text(
                f"� <b>File downloaded</b>\n"
                f"✅ <b>Processed {lines_processed} lines</b>\n"
                f"🧹 <b>Cleaned {lines_cleaned} URLs</b>\n"
                f"�🔄 Connecting to FTP...",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error cleaning file: {e}")
            if os.path.exists(cleaned_tmp_path):
                os.unlink(cleaned_tmp_path)
            await status_msg.edit_text(
                "📦 <b>File downloaded</b>\n"
                "⚠️ Could not clean URLs, uploading as-is...\n"
                "🔄 Connecting to FTP...",
                parse_mode='HTML'
            )
            lines_processed = 0
            lines_cleaned = 0
        
        ftp = FTP_TLS(timeout=30)
        ftp.connect(config['host'], config['port'])
        ftp.login(config['user'], config['pass'])
        ftp.prot_p()
        
        await status_msg.edit_text(
            f"📦 <b>File downloaded</b>\n"
            f"✅ <b>Connected to FTP</b>\n"
            f"📂 Navigating to {config['path']}...",
            parse_mode='HTML'
        )
        
        ftp.cwd(config['path'])
        
        original_filename = document.file_name if document.file_name else "upload.txt"
        temp_upload_name = original_filename
        target_filename = 'pullzone_hostnames.txt'
        
        logger.info(f"Original filename: {original_filename}")
        
        await status_msg.edit_text(
            f"📦 <b>File downloaded</b>\n"
            f"✅ <b>Connected to FTP</b>\n"
            f"📂 <b>In directory</b>\n"
            f"📤 Uploading as <code>{temp_upload_name}</code>...",
            parse_mode='HTML'
        )
        
        with open(tmp_path, 'rb') as f:
            ftp.storbinary(f'STOR {temp_upload_name}', f)
        
        logger.info(f"File uploaded as {temp_upload_name}, size: {file_size_bytes} bytes")
        
        await status_msg.edit_text(
            f"📦 <b>File downloaded</b>\n"
            f"✅ <b>Connected to FTP</b>\n"
            f"📂 <b>In directory</b>\n"
            f"✅ <b>File uploaded</b>\n"
            f"📋 Listing directory...",
            parse_mode='HTML'
        )
        
        files = ftp.nlst()
        logger.info(f"Directory listing: {files}")
        
        old_file_deleted = False
        if target_filename in files:
            await status_msg.edit_text(
                f"📦 <b>File downloaded</b>\n"
                f"✅ <b>Connected to FTP</b>\n"
                f"📂 <b>In directory</b>\n"
                f"✅ <b>File uploaded</b>\n"
                f"🗑️ Deleting old {target_filename}...",
                parse_mode='HTML'
            )
            ftp.delete(target_filename)
            old_file_deleted = True
            logger.info(f"Deleted old {target_filename}")
        
        await status_msg.edit_text(
            f"📦 <b>File downloaded</b>\n"
            f"✅ <b>Connected to FTP</b>\n"
            f"📂 <b>In directory</b>\n"
            f"✅ <b>File uploaded</b>\n"
            f"{('🗑️ <b>Old file deleted</b>' if old_file_deleted else 'ℹ️ <b>No old file</b>')}\n"
            f"🔄 Renaming to {target_filename}...",
            parse_mode='HTML'
        )
        
        ftp.rename(temp_upload_name, target_filename)
        logger.info(f"Renamed {temp_upload_name} to {target_filename}")
        
        cleanup_files = ['.next_index', 'assignments.log']
        cleaned = []
        
        await status_msg.edit_text(
            f"📦 <b>File downloaded</b>\n"
            f"✅ <b>Connected to FTP</b>\n"
            f"📂 <b>In directory</b>\n"
            f"✅ <b>File uploaded</b>\n"
            f"{('🗑️ <b>Old file deleted</b>' if old_file_deleted else 'ℹ️ <b>No old file</b>')}\n"
            f"✅ <b>Renamed to {target_filename}</b>\n"
            f"🧹 Cleaning up...",
            parse_mode='HTML'
        )
        
        for cleanup_file in cleanup_files:
            try:
                if cleanup_file in files:
                    ftp.delete(cleanup_file)
                    cleaned.append(cleanup_file)
                    logger.info(f"Deleted {cleanup_file}")
            except Exception as e:
                logger.info(f"Could not delete {cleanup_file}: {e}")
        
        cleanup_text = f"🧹 Cleaned: {', '.join(cleaned)}" if cleaned else ""
        
        success_details = (
            f"✅ <b>Upload Successful!</b>\n\n"
            f"📥 Original: <code>{original_filename}</code>\n"
            f"📄 Saved as: <code>{target_filename}</code>\n"
            f"📂 Location: <code>{config['path']}/</code>\n"
            f"💾 Size: {file_size_bytes:,} bytes ({file_size_mb:.2f} MB)\n"
        )
        
        if lines_cleaned > 0:
            success_details += f"🧹 Cleaned {lines_cleaned}/{lines_processed} URLs\n"
        
        success_details += f"\n{('🗑️ Old file replaced' if old_file_deleted else '🆕 New file created')}\n"
        
        if cleanup_text:
            success_details += cleanup_text
        
        await status_msg.edit_text(
            success_details,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except error_perm as e:
        error_msg = (
            f"❌ <b>FTP Permission Error</b>\n\n"
            f"Details: <code>{str(e)}</code>\n\n"
            f"Check if you have write permissions."
        )
        await status_msg.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    except TimeoutError:
        error_msg = (
            f"❌ <b>Connection Timeout</b>\n\n"
            f"The FTP server is not responding.\n"
            f"Please try again later."
        )
        await status_msg.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Upload error: {e}\n{traceback.format_exc()}")
        error_msg = (
            f"❌ <b>Upload Failed</b>\n\n"
            f"Error: <code>{str(e)}</code>\n\n"
            f"Please try again or check your FTP settings."
        )
        await status_msg.edit_text(
            error_msg,
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
    finally:
        if ftp:
            try:
                ftp.quit()
            except:
                try:
                    ftp.close()
                except:
                    pass
        
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.error(f"Error deleting temp file: {e}")
    
    return ConversationHandler.END

async def upload_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(
            "❌ Upload cancelled.",
            reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in upload_cancel: {e}")
    return ConversationHandler.END

async def view_config(query, user_id):
    config = load_ftp_config(user_id)
    
    if not config:
        await query.edit_message_text(
            "❌ <b>No Configuration Found</b>\n\n"
            "Please setup your FTP credentials first.",
            parse_mode='HTML',
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    
    masked_pass = config['pass'][:2] + '*' * (len(config['pass']) - 4) + config['pass'][-2:] if len(config['pass']) > 4 else '****'
    
    keyboard = [
        [InlineKeyboardButton("🔄 Update Config", callback_data="menu_setup")],
        [InlineKeyboardButton("🗑️ Delete Config", callback_data="delete_config")],
        [InlineKeyboardButton("🏠 Back to Menu", callback_data="menu_main")]
    ]
    
    await query.edit_message_text(
        "💾 <b>Saved FTP Configuration</b>\n\n"
        f"📡 <b>Host:</b> <code>{config['host']}</code>\n"
        f"🔌 <b>Port:</b> <code>{config['port']}</code>\n"
        f"👤 <b>Username:</b> <code>{config['user']}</code>\n"
        f"🔒 <b>Password:</b> <code>{masked_pass}</code>\n"
        f"📂 <b>Path:</b> <code>{config['path']}</code>\n\n"
        f"💡 <b>Config file:</b> ftp_config.json\n"
        f"✅ This configuration is <b>permanent</b> - saved locally!",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_config(query, user_id):
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="confirm_delete")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_view_config")]
    ]
    
    await query.edit_message_text(
        "⚠️ <b>Delete FTP Configuration?</b>\n\n"
        "Are you sure you want to delete your saved FTP credentials?\n\n"
        "You'll need to setup again to upload files.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_delete_config(query, user_id):
    try:
        if os.path.exists(FTP_CONFIG_FILE):
            with open(FTP_CONFIG_FILE, 'r') as f:
                configs = json.load(f)
            
            if str(user_id) in configs:
                del configs[str(user_id)]
                
                with open(FTP_CONFIG_FILE, 'w') as f:
                    json.dump(configs, f, indent=2)
                
                logger.info(f"Config deleted for user {user_id}")
                
                await query.edit_message_text(
                    "✅ <b>Configuration Deleted</b>\n\n"
                    "Your FTP credentials have been removed.\n"
                    "Use Setup to configure again.",
                    parse_mode='HTML',
                    reply_markup=get_back_to_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    "ℹ️ No configuration found to delete.",
                    reply_markup=get_back_to_menu_keyboard()
                )
        else:
            await query.edit_message_text(
                "ℹ️ No configuration found to delete.",
                reply_markup=get_back_to_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        await query.edit_message_text(
            f"❌ Error deleting configuration: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "menu_main":
            user = query.from_user
            config = load_ftp_config(user.id)
            
            if config:
                status_text = "✅ <b>Configured & Saved</b> (Permanent)"
                info_text = "Your FTP credentials are saved and ready!"
            else:
                status_text = "❌ Not configured"
                info_text = "Setup once - saved permanently!"
            
            await query.edit_message_text(
                f"🤖 <b>FTP Pullzone Bot</b>\n\n"
                f"FTP Status: {status_text}\n"
                f"{info_text}\n\n"
                f"Select an option below:",
                parse_mode='HTML',
                reply_markup=get_main_menu_keyboard(has_config=bool(config))
            )
        
        elif query.data == "menu_setup":
            await setup_start(query, context, is_callback=True)
        
        elif query.data == "menu_upload":
            return await upload_start(query, context, is_callback=True)
        
        elif query.data == "menu_status":
            await test_connection(query, query.from_user.id, is_callback=True)
        
        elif query.data == "menu_help":
            await show_help(query, is_callback=True)
        
        elif query.data == "menu_view_config":
            await view_config(query, query.from_user.id)
        
        elif query.data == "delete_config":
            await delete_config(query, query.from_user.id)
        
        elif query.data == "confirm_delete":
            await confirm_delete_config(query, query.from_user.id)
        
        elif query.data == "cancel_setup":
            await query.edit_message_text(
                "❌ Setup cancelled.",
                reply_markup=get_back_to_menu_keyboard()
            )
            return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"Error in button_handler: {e}\n{traceback.format_exc()}")
        try:
            await query.edit_message_text(
                f"❌ An error occurred: {str(e)}\n\n"
                f"Please try again.",
                reply_markup=get_back_to_menu_keyboard()
            )
        except:
            pass

def main():
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error("Please set the token in Replit Secrets")
        return
    
    try:
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("✅ Flask keep-alive server started on port 8080")
    except Exception as e:
        logger.error(f"⚠️ Flask server failed to start: {e}")
    
    try:
        application = Application.builder().token(TOKEN).build()
        
        setup_handler = ConversationHandler(
            entry_points=[
                CommandHandler('setup', lambda u, c: setup_start(u, c, is_callback=False)),
                CallbackQueryHandler(button_handler, pattern="^menu_setup$")
            ],
            states={
                FTP_HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ftp_host)],
                FTP_PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ftp_port)],
                FTP_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ftp_user)],
                FTP_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ftp_pass)],
                FTP_PATH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ftp_path)],
            },
            fallbacks=[
                CommandHandler('cancel', setup_cancel),
                CallbackQueryHandler(button_handler, pattern="^cancel_setup$")
            ],
            allow_reentry=True
        )
        
        upload_handler = ConversationHandler(
            entry_points=[
                CommandHandler('upload', lambda u, c: upload_start(u, c, is_callback=False)),
                CallbackQueryHandler(button_handler, pattern="^menu_upload$")
            ],
            states={
                UPLOAD_FILE: [MessageHandler(filters.Document.ALL, upload_file)],
            },
            fallbacks=[CommandHandler('cancel', upload_cancel)],
            allow_reentry=True
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", lambda u, c: show_help(u, is_callback=False)))
        application.add_handler(CommandHandler("status", lambda u, c: test_connection(u, u.effective_user.id, is_callback=False)))
        application.add_handler(setup_handler)
        application.add_handler(upload_handler)
        application.add_handler(CallbackQueryHandler(button_handler))
        
        logger.info("🤖 Bot started successfully!")
        logger.info("📡 Listening for updates...")
        
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}\n{traceback.format_exc()}")

if __name__ == '__main__':
    main()
