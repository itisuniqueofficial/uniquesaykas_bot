import os
import json
import requests
import feedparser
import logging
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the base folder to store user and group commands
BASE_COMMANDS_FOLDER = "bot_commands"

# Ensure the base commands folder exists
os.makedirs(BASE_COMMANDS_FOLDER, exist_ok=True)

# Function to get current timestamp in GMT+05:30
def get_timestamp():
    gmt_offset = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(gmt_offset).strftime('%Y-%m-%d %H:%M:%S')

# Load commands from JSON files
def load_commands(id_type, id_value):
    commands = {}
    folder_path = os.path.join(BASE_COMMANDS_FOLDER, f"{id_type}_{id_value}")

    # Ensure the user's or group's folder exists
    os.makedirs(folder_path, exist_ok=True)

    # Load commands from the specific folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            with open(os.path.join(folder_path, filename), 'r') as f:
                commands.update(json.load(f))
    return commands

# Save commands to JSON files
def save_commands(id_type, id_value, commands):
    folder_path = os.path.join(BASE_COMMANDS_FOLDER, f"{id_type}_{id_value}")
    os.makedirs(folder_path, exist_ok=True)

    with open(os.path.join(folder_path, "commands.json"), 'w') as f:
        json.dump(commands, f)

# Fetch news from the Blaze Times RSS feed
def get_blaze_times_news():
    feed_url = "https://www.theblazetimes.in/feed.xml"
    try:
        feed = feedparser.parse(feed_url)
        if feed.bozo:
            return "Failed to fetch news from Blaze Times."

        news_items = []
        for entry in feed.entries[:5]:  # Get the top 5 news articles
            title = entry.title
            link = entry.link
            published = entry.published
            news_items.append(f"📰 *{title}*\n_{published}_\n[Read more]({link})")

        return "\n\n".join(news_items) if news_items else "No news found."
    except Exception as e:
        return f"An error occurred while fetching news: {str(e)}"

# Start Command Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use /help to see available commands.")
    logging.info(f"User {update.message.from_user.id} started the bot.")

# Help Command Handler
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "Here are the commands you can use:\n"
    help_text += "\n".join([
        "/addcommand \"<command>\" answer - Save a custom command (admins only).",
        "/mycommands - List your saved commands (admins only).",
        "/deletecommand <command> - Delete a saved command (admins only).",
        "/theblazetimes - Get the latest news from Blaze Times."
    ])
    await update.message.reply_text(help_text)
    logging.info(f"User {update.message.from_user.id} requested help.")

# Enhanced Add Command Handler
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    logging.info(f"User {user_id} attempted to add a command: {update.message.text}")

    # Check if the user is an admin or owner
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins and owners can add commands.")
        return

    # Match the new format: "<command>" answer
    match = re.match(r'\"(.+?)\"\s+(.+)', update.message.text[12:].strip())
    if match:
        command, answer = match.groups()
        command = command.strip().lower()

        # Load existing commands for this group/user
        id_type = 'group' if update.effective_chat.type in ['group', 'supergroup'] else 'user'
        commands = load_commands(id_type, chat_id)

        # Prevent duplicate commands
        if command not in commands:
            commands[command] = answer
            save_commands(id_type, chat_id, commands)
            await update.message.reply_text(f"Command '{command}' saved with answer: {answer}")
            logging.info(f"Command '{command}' added by user {user_id}.")
        else:
            await update.message.reply_text(f"Command '{command}' already exists in this {id_type}.")
    else:
        await update.message.reply_text("Invalid format. Use:\n/addcommand \"<command>\" answer")

# List All User Commands Handler
async def my_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    logging.info(f"User {user_id} requested their commands.")

    # Check if the user is an admin or owner
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins and owners can view commands.")
        return

    commands = load_commands('group' if update.effective_chat.type in ['group', 'supergroup'] else 'user', chat_id)
    if commands:
        command_list = "\n".join([f"{cmd}: {ans}" for cmd, ans in commands.items()])
        await update.message.reply_text(f"Commands:\n{command_list}")
    else:
        await update.message.reply_text("No commands found.")

# Delete Command Handler
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    if chat_member.status not in ['administrator', 'creator']:
        await update.message.reply_text("Only admins and owners can delete commands.")
        return

    command = " ".join(context.args).strip().lower()
    commands = load_commands('group' if update.effective_chat.type in ['group', 'supergroup'] else 'user', chat_id)
    if command in commands:
        del commands[command]
        save_commands('group' if update.effective_chat.type in ['group', 'supergroup'] else 'user', chat_id, commands)
        await update.message.reply_text(f"Command '{command}' has been deleted.")
    else:
        await update.message.reply_text(f"Command '{command}' not found.")

# Blaze Times News Command Handler
async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    blaze_news_text = get_blaze_times_news()
    await update.message.reply_text(blaze_news_text, parse_mode="Markdown")

# Message Handler to Match User and Group Commands
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip().lower()
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id

    commands = load_commands('group' if update.effective_chat.type in ['group', 'supergroup'] else 'user', chat_id)
    if message_text in commands:
        await update.message.reply_text(commands[message_text])
    else:
        logging.info(f"Command '{message_text}' not found for user {user_id} in chat {chat_id}.")

# Main Function to Set Up the Bot
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
