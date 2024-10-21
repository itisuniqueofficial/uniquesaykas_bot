import os
import json
import re
import logging
import feedparser
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the base folder to store commands
BASE_COMMANDS_FOLDER = "bot_commands"
os.makedirs(BASE_COMMANDS_FOLDER, exist_ok=True)  # Ensure folder exists

# Function to get timestamp in GMT+05:30
def get_timestamp():
    gmt_offset = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(gmt_offset).strftime('%Y-%m-%d %H:%M:%S')

# Function to load commands from JSON
def load_commands(id_type, id_value):
    folder_path = os.path.join(BASE_COMMANDS_FOLDER, f"{id_type}_{id_value}")
    os.makedirs(folder_path, exist_ok=True)

    try:
        with open(os.path.join(folder_path, "commands.json"), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Function to save commands to JSON
def save_commands(id_type, id_value, commands):
    folder_path = os.path.join(BASE_COMMANDS_FOLDER, f"{id_type}_{id_value}")
    os.makedirs(folder_path, exist_ok=True)

    with open(os.path.join(folder_path, "commands.json"), 'w', encoding='utf-8') as f:
        json.dump(commands, f, ensure_ascii=False, indent=4)

# Fetch latest Blaze Times news
def get_blaze_times_news():
    feed_url = "https://www.theblazetimes.in/feed.xml"
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            return "Failed to fetch news from Blaze Times."

        news_items = [
            f"📰 *{entry.title}*\n_{entry.published}_\n[Read more]({entry.link})"
            for entry in feed.entries[:5]
        ]
        return "\n\n".join(news_items) if news_items else "No news found."
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /help to see available commands.")
    logging.info(f"User {update.message.from_user.id} started the bot.")

# Help command handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Here are the commands you can use:\n"
        "/addcommand \"<command>\" <answer> - Save a custom command (admins only).\n"
        "/mycommands - List your saved commands (admins only).\n"
        "/deletecommand <command> - Delete a saved command (admins only).\n"
        "/theblazetimes - Get the latest news from Blaze Times."
    )
    await update.message.reply_text(help_text)

# Add command handler
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    # Check if user is admin or owner
    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins can add commands.")
        return

    # Match command and answer
    match = re.match(r'"(.+?)"\s+([\s\S]+)', update.message.text[12:].strip())
    if match:
        command, answer = match.groups()
        command = command.strip().lower()

        # Load existing commands
        id_type = 'group' if update.effective_chat.type in ['group', 'supergroup'] else 'user'
        commands = load_commands(id_type, chat_id)

        if command not in commands:
            commands[command] = answer
            save_commands(id_type, chat_id, commands)
            await update.message.reply_text(f"Command '{command}' saved:\n\n{answer}")
        else:
            await update.message.reply_text(f"Command '{command}' already exists.")
    else:
        await update.message.reply_text("Invalid format. Use:\n/addcommand \"<command>\" <answer>")

# List commands handler
async def my_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins can view commands.")
        return

    id_type = 'group' if update.effective_chat.type in ['group', 'supergroup'] else 'user'
    commands = load_commands(id_type, chat_id)

    if commands:
        command_list = "\n".join([f"{cmd}: {ans}" for cmd, ans in commands.items()])
        await update.message.reply_text(f"Commands:\n{command_list}", parse_mode="MarkdownV2")
    else:
        await update.message.reply_text("No commands found.")

# Delete command handler
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    chat_member = await context.bot.get_chat_member(chat_id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins can delete commands.")
        return

    command = " ".join(context.args).strip().lower()
    id_type = 'group' if update.effective_chat.type in ['group', 'supergroup'] else 'user'
    commands = load_commands(id_type, chat_id)

    if command in commands:
        del commands[command]
        save_commands(id_type, chat_id, commands)
        await update.message.reply_text(f"Command '{command}' has been deleted.")
    else:
        await update.message.reply_text(f"Command '{command}' not found.")

# News command handler
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    blaze_news_text = get_blaze_times_news()
    await update.message.reply_text(blaze_news_text, parse_mode="Markdown")

# Message handler to respond to saved commands
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip().lower()
    chat_id = update.effective_chat.id

    id_type = 'group' if update.effective_chat.type in ['group', 'supergroup'] else 'user'
    commands = load_commands(id_type, chat_id)

    if message_text in commands:
        await update.message.reply_text(commands[message_text], parse_mode="MarkdownV2")
    else:
        logging.info(f"Command '{message_text}' not found.")

# Main function to start the bot
def main():
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addcommand", add_command))
    app.add_handler(CommandHandler("mycommands", my_commands))
    app.add_handler(CommandHandler("deletecommand", delete_command))
    app.add_handler(CommandHandler("theblazetimes", news))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
