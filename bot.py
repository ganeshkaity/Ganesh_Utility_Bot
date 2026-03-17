import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)
from utils import GroqChatWrapper, YouTubeDownloader, ImageGenerator, InstagramDownloader, cleanup_file

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
MAIN, CHAT, YT_WAIT, YT_LINK, IG_WAIT, IMG_PROMPT, IMG_MODEL, IMG_WIDTH, IMG_HEIGHT = range(9)

# Initialize Wrappers
groq_chat = GroqChatWrapper(GROQ_API_KEY)
yt = YouTubeDownloader()
ig = InstagramDownloader()
img_gen = ImageGenerator(HF_API_KEY)

# Keyboards
def get_main_menu_keyboard():
    keyboard = [
        ["💬 Chat with AI"],
        ["🎵 YouTube → Audio", "🔗 YouTube Video Link"],
        ["🎨 Image Generator", "📲 Instagram Reel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_menu_keyboard():
    return ReplyKeyboardMarkup([["Main Menu"]], resize_keyboard=True)

def get_image_models_keyboard():
    models = {
        "flux": "Flux (Fast)",
        "stable-diffusion-xl": "Stable Diffusion XL",
        "openjourney": "OpenJourney",
        "dreamshaper": "DreamShaper XL",
        "anime": "Animagine XL",
    }
    keyboard = [[InlineKeyboardButton(label, callback_data=f'img_model_{key}')] for key, label in models.items()]
    return InlineKeyboardMarkup(keyboard)

def get_help_text():
    return (
        "🤖 **Multi-Utility Bot Help**\n\n"
        "You can use the menu buttons below or these commands:\n\n"
        "🎵 **Audio & Video**\n"
        "• `/play <query/url>` - Download YouTube Audio\n"
        "• `/video <query/url>` - Get YouTube Video Link\n"
        "• `/ig <url>` - Get Instagram Reel Link\n\n"
        "🎨 **Images**\n"
        "• `/imagine <prompt>` - Generate AI Image\n\n"
        "💬 **AI Chat**\n"
        "• Just tap 'Chat with AI' to start talking.\n\n"
        "💡 **Tip**: If the menu disappears, type `/start` to bring it back!"
    )

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message and the main menu."""
    welcome_text = "👋 **Welcome to the Multi-Utility Bot!**\n\n" + get_help_text()
    # If starting from a text command, remove any existing reply keyboards
    await update.message.reply_text("Loading...", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_main_menu_keyboard())
    return MAIN

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the main menu button from any state."""
    query = update.callback_query
    await query.answer()
    
    # Clear user data related to states if necessary
    context.user_data.clear()
    
    await query.edit_message_text(
        "Loading...",
        reply_markup=None
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome back! Choose a feature below:",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN

async def main_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles 'Main Menu' text to return to main menu and remove reply keyboard."""
    context.user_data.clear()
    # Remove the reply keyboard
    await update.message.reply_text("Returning to main menu...", reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text(
        "Welcome back! Choose a feature below:",
        reply_markup=get_main_menu_keyboard()
    )
    return MAIN

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes main menu selections."""
    text = update.message.text
    
    if text == '💬 Chat with AI':
        await update.message.reply_text(
            "Chat freely with AI. Press the 'Main Menu' button below to exit.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return CHAT
    elif text == '🎵 YouTube → Audio':
        await update.message.reply_text(
            "Send a YouTube URL or video name. I'll download the audio for you.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return YT_WAIT
    elif text == '🔗 YouTube Video Link':
        await update.message.reply_text(
            "Send a YouTube URL or video name. I'll get the direct video link for you.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return YT_LINK
    elif text == '📲 Instagram Reel':
        await update.message.reply_text(
            "Send an Instagram Reel URL. I'll get the direct video link for you.",
            reply_markup=get_back_to_menu_keyboard()
        )
        return IG_WAIT
    elif text == '🎨 Image Generator':
        await update.message.reply_text(
            "Please enter a text prompt for the image generator:",
            reply_markup=get_back_to_menu_keyboard()
        )
        return IMG_PROMPT
    
    # Help fallthrough for unknown text
    else:
        await update.message.reply_text(get_help_text(), parse_mode='Markdown', reply_markup=get_main_menu_keyboard())
        return MAIN

# --- CHAT FLOW ---
async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if user_text.lower() in ['main', 'main menu']:
        return await main_menu_message(update, context)
    
    # Keep history in user_data
    if 'chat_history' not in context.user_data:
        context.user_data['chat_history'] = []
    
    # Send 'typing' action and a visible "Thinking..." message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    thinking_msg = await update.message.reply_text("Thinking... 💭")
    
    response = await groq_chat.generate_response(user_text, history=context.user_data['chat_history'])
    
    # Delete the "Thinking..." message
    await thinking_msg.delete()
    
    # Update history (keep last 20 messages / 10 turns)
    context.user_data['chat_history'].append({"role": "user", "content": user_text})
    context.user_data['chat_history'].append({"role": "assistant", "content": response})
    context.user_data['chat_history'] = context.user_data['chat_history'][-20:]
    
    await update.message.reply_text(response, reply_markup=get_back_to_menu_keyboard())
    return CHAT

# --- YT FLOW ---
async def handle_youtube_download(query: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("Fetching audio link... 🎵")
    
    result = await yt.get_audio_url(query)
    await status_msg.delete()
    if result:
        audio_url, title = result
        await update.message.reply_text(
            f"🎵 **Audio Title:** {title}\n\n🔗 **Direct Link:** [Click here to download]({audio_url})",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text("Sorry, I couldn't get the audio link. ❌", reply_markup=get_main_menu_keyboard())


async def youtube_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if query.lower() in ['main', 'main menu']:
        return await main_menu_message(update, context)
    
    await handle_youtube_download(query, update, context)
    return MAIN

async def handle_youtube_link(query: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("Fetching video link... 🔗")
    
    result = await yt.get_video_url(query)
    await status_msg.delete()
    if result:
        video_url, title = result
        await update.message.reply_text(
            f"🎬 **Title:** {title}\n\n🔗 **Direct Link:** [Click here to download]({video_url})",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text("Sorry, I couldn't get the video link. ❌", reply_markup=get_main_menu_keyboard())

async def youtube_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if query.lower() in ['main', 'main menu']:
        return await main_menu_message(update, context)
    
    await handle_youtube_link(query, update, context)
    return MAIN

# --- IG FLOW ---
async def handle_instagram_reel(url: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("Fetching Instagram Reel... 📲")
    
    result = await ig.get_reel_url(url)
    await status_msg.delete()
    if result:
        video_url, title = result
        await update.message.reply_text(
            f"📲 **Reel:** {title}\n\n🔗 **Direct Link:** [Click here to download]({video_url})",
            parse_mode='Markdown',
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text("Sorry, I couldn't get the Reel link. ❌\nMake sure the URL is public.", reply_markup=get_main_menu_keyboard())

async def instagram_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if url.lower() in ['main', 'main menu']:
        return await main_menu_message(update, context)
    
    await handle_instagram_reel(url, update, context)
    return MAIN

# --- IMAGE FLOW ---
async def handle_image_generation(prompt: str, model: str, width: int, height: int, update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("Generating your image... 🎨")
    
    async def process_img():
        image_data = await img_gen.generate_image(prompt, model, width, height)
        
        if image_data:
            await update.message.reply_photo(
                photo=image_data,
                caption=f"Prompt: {prompt}\nModel: {model}\nSize: {width}x{height}",
                reply_markup=get_main_menu_keyboard()
            )
            await status_msg.delete()
        else:
            await status_msg.delete()
            await update.message.reply_text("Failed to generate image. ❌", reply_markup=get_main_menu_keyboard())

    asyncio.create_task(process_img())


async def img_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    if prompt.lower() in ['main', 'main menu']:
        return await main_menu_message(update, context)
    
    context.user_data['img_prompt'] = prompt
    await update.message.reply_text("Choose a model:", reply_markup=get_image_models_keyboard())
    return IMG_MODEL

async def img_model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    model = query.data.replace('img_model_', '')
    context.user_data['img_model'] = model
    
    await query.edit_message_text(f"Model selected: {model}. Now enter width (e.g., 1024):")
    return IMG_WIDTH

async def img_width_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        width = int(update.message.text)
        context.user_data['img_width'] = width
        await update.message.reply_text("Now enter height (e.g., 1024):")
        return IMG_HEIGHT
    except ValueError:
        await update.message.reply_text("Please enter a valid number for width.")
        return IMG_WIDTH

async def img_height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = int(update.message.text)
        context.user_data['img_height'] = height
        
        prompt = context.user_data['img_prompt']
        model = context.user_data['img_model']
        width = context.user_data['img_width']
        
        await handle_image_generation(prompt, model, width, height, update, context)
        return MAIN
        
    except ValueError:
        await update.message.reply_text("Please enter a valid number for height.")
        return IMG_HEIGHT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.", reply_markup=get_main_menu_keyboard())
    return MAIN


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_help_text(), parse_mode='Markdown', reply_markup=get_main_menu_keyboard())
    return MAIN

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a search term or URL.\nExample: /play shape of you", reply_markup=get_main_menu_keyboard())
        return MAIN
    query = " ".join(context.args)
    await handle_youtube_download(query, update, context)
    return MAIN

async def imagine_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a prompt.\nExample: /imagine a futuristic city", reply_markup=get_main_menu_keyboard())
        return MAIN
    prompt = " ".join(context.args)
    model = "flux" 
    width = 1024
    height = 1024
    await handle_image_generation(prompt, model, width, height, update, context)
    return MAIN

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a search term or URL.\nExample: /video shape of you", reply_markup=get_main_menu_keyboard())
        return MAIN
    query = " ".join(context.args)
    await handle_youtube_link(query, update, context)
    return MAIN

async def ig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an Instagram Reel URL.\nExample: /ig https://www.instagram.com/reels/...", reply_markup=get_main_menu_keyboard())
        return MAIN
    url = clean_url(context.args[0]) if 'clean_url' in globals() else context.args[0]
    # Simple check for URL
    if not url.startswith("http"):
        await update.message.reply_text("Invalid URL. Please provide a full link.")
        return MAIN
    await handle_instagram_reel(url, update, context)
    return MAIN

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment.")
        return

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(60.0)
        .read_timeout(120.0)
        .write_timeout(120.0)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('help', help_command),
            CommandHandler(['play', 'download'], play_command),
            CommandHandler(['imagine', 'create'], imagine_command),
            CommandHandler(['video', 'link'], video_command),
            CommandHandler(['ig', 'reel'], ig_command),
            MessageHandler(filters.Regex('(?i)^(main|main menu)$'), main_menu_message)
        ],
        states={
            MAIN: [
                MessageHandler(filters.Regex('^(💬 Chat with AI|🎵 YouTube → Audio|🔗 YouTube Video Link|🎨 Image Generator|📲 Instagram Reel)$'), menu_router),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
                MessageHandler(filters.Regex('(?i)^(main|main menu)$'), main_menu_message)
            ],
            CHAT: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), chat_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            YT_WAIT: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), youtube_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            YT_LINK: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), youtube_link_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            IG_WAIT: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), instagram_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            IMG_PROMPT: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), img_prompt_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$')
            ],
            IMG_MODEL: [
                CallbackQueryHandler(img_model_callback, pattern='^img_model_'),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
                MessageHandler(filters.Regex('(?i)^(main|main menu)$'), main_menu_message)
            ],
            IMG_WIDTH: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), img_width_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
                MessageHandler(filters.Regex('(?i)^(main|main menu)$'), main_menu_message)
            ],
            IMG_HEIGHT: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), img_height_handler),
                CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'),
                MessageHandler(filters.Regex('(?i)^(main|main menu)$'), main_menu_message)
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('help', help_command),
            CommandHandler(['play', 'download'], play_command),
            CommandHandler(['imagine', 'create'], imagine_command),
            CommandHandler(['video', 'link'], video_command),
            CommandHandler(['ig', 'reel'], ig_command)
        ],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    
    application.add_handler(CommandHandler('help', help_command))
    
    # Global menu button handler for when outside of conv handler triggers
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^main_menu$'))

    print("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
