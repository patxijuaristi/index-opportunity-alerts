# Telegram Bot Setup Guide

## 1. Create a Telegram Bot

Open Telegram and search for:

@BotFather

Start a conversation and run:

/newbot

You will be asked to provide:

* Bot name (e.g. Nasdaq DCA Alert)
* Username (must end with "bot")

Example:

`nasdaq_dca_alert_bot`

After creation, BotFather will give you a token:

Example:

`123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

Save this securely. It will be used as:

`TELEGRAM_BOT_TOKEN`

---

## 2. Get Your Chat ID

1. Open your bot in Telegram
2. Press START
3. Open in browser:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Example:

```
https://api.telegram.org/bot123456789:AAxxxxxxxxxxxx/getUpdates
```

4. Look for:

```
"chat": {
    "id": 123456789
}
```

The numeric value is your:

`TELEGRAM_CHAT_ID`

---

## 3. Configure GitHub Secrets

In your repository:

Settings → Secrets and variables → Actions

Add:

```
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

---

## 4. Test the Bot

Run the GitHub Actions workflow manually.

If everything is correct, you should receive a Telegram message.

---

## 5. Security Notes

* Never commit the bot token to the repository
* Always use GitHub Secrets for credentials
* Rotate tokens if they are exposed
