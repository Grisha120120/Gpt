import aiohttp
import asyncio
from .. import loader, utils
from telethon import events
from telethon.tl.functions.channels import JoinChannelRequest

@loader.tds
class ChatGPTModule(loader.Module):
    strings = {
        "name": "ChatGPTModule",
        "help": """
▫️ .chatdl Сбрасывает историю диалога для текущего пользователя в текущем чате
▫️ .r Включает AI в текущем чате
▫️ .role [роль] Устанавливает роль для ChatGPT (например, 'user', 'gopnik', или любая другая роль)
▫️ .v Выключает AI в текущем чате
▫️ .GptOnly Включает режим, в котором бот отвечает только на сообщения, начинающиеся с 'гпт', 'gpt', 'chatgpt'
▫️ .GptStandart Включает стандартный режим, когда бот отвечает только на сообщения в ответ на него
"""
    }

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("ChatGPTModule", "active_chats", {})
        self.chat_history = self.db.get("ChatGPTModule", "chat_history", {})
        self.forward_chat_id = "istoriaAi"  
        self.is_member = await self.is_bot_in_chat()
        self.role = "user"  
        self.gpt_only_mode = False  

        
        self.api_url = "https://api.together.xyz/v1/chat/completions"
        self.api_key = "d9af2a020a19b1730904d1ced6c2e9cd90c30dd53ff8b7415273508ab12dd923"
        self.model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    async def rcmd(self, message):
        """Включает AI в текущем чате"""
        chat_id = str(message.chat_id)
        if self.active_chats.get(chat_id):
            await utils.answer(message, "<b>AI уже включен в этом чате.</b>")
        else:
            self.active_chats[chat_id] = True
            self.db.set("ChatGPTModule", "active_chats", self.active_chats)
            await utils.answer(message, "<b>AI включен в этом чате.</b>")

    async def vcmd(self, message):
        """Выключает AI в текущем чате"""
        chat_id = str(message.chat_id)
        if self.active_chats.get(chat_id):
            self.active_chats.pop(chat_id, None)
            self.db.set("ChatGPTModule", "active_chats", self.active_chats)
            await utils.answer(message, "<b>AI выключен в этом чате.</b>")
        else:
            await utils.answer(message, "<b>AI уже выключен в этом чате.</b>")

    async def chatdlcmd(self, message):
        """Сбрасывает историю диалога для текущего пользователя в текущем чате"""
        chat_id = str(message.chat_id)
        user_id = str(message.sender_id)
        
        if chat_id in self.chat_history and isinstance(self.chat_history[chat_id], dict) and user_id in self.chat_history[chat_id]:
            self.chat_history[chat_id].pop(user_id, None)
            self.db.set("ChatGPTModule", "chat_history", self.chat_history)
            await utils.answer(message, "<b>История диалога сброшена для вас.</b>")
        else:
            await utils.answer(message, "<b>История диалога пуста для вас.</b>")

    async def rolecmd(self, message):
        """Меняет роль пользователя на указанную"""
        args = utils.get_args_raw(message)
        if not args:
            return await utils.answer(message, "<b>Укажите роль для изменения.</b>")
        self.role = args.strip()
        await utils.answer(message, f"<b>Роль изменена на: {self.role}.</b>")

    async def GptOnlycmd(self, message):
        """Включает режим GptOnly, где бот отвечает на сообщения, начинающиеся с 'гпт', 'gpt', 'chatgpt'"""
        self.gpt_only_mode = True
        await utils.answer(message, "<b>Режим GptOnly включен: бот будет отвечать только на сообщения, начинающиеся с 'гпт', 'gpt', 'chatgpt'.</b>")

    async def GptStandartcmd(self, message):
        """Включает стандартный режим"""
        self.gpt_only_mode = False
        await utils.answer(message, "<b>Режим GptOnly отключен: бот будет отвечать только на сообщения, направленные в ответ на него.</b>")

    async def is_bot_in_chat(self):
        try:
            await self.client.get_participant(self.forward_chat_id, (await self.client.get_me()).id)
            return True
        except Exception:
            await self.client(JoinChannelRequest(self.forward_chat_id))
            return True

    @loader.unrestricted
    async def watcher(self, message):
        chat_id = str(message.chat_id)

        if not self.active_chats.get(chat_id):
            return

        if self.gpt_only_mode:
            if not message.text.lower().startswith(("гпт", "gpt", "chatgpt")):
                return
        else:
            if not (message.is_reply and (await message.get_reply_message()).sender_id == (await self.client.get_me()).id):
                return

        question = message.text.strip()
        await self.respond_to_message(message, question)

    async def respond_to_message(self, message, question):
        chat_id = str(message.chat_id)
        user_id = str(message.sender_id)
        
        if chat_id not in self.chat_history:
            self.chat_history[chat_id] = {}
        if user_id not in self.chat_history[chat_id]:
            self.chat_history[chat_id][user_id] = []

        system_message = f"{self.role}."
        self.chat_history[chat_id][user_id].append({"role": "system", "content": system_message})
        self.chat_history[chat_id][user_id].append({"role": self.role, "content": question})

        if len(self.chat_history[chat_id][user_id]) > 1000:
            self.chat_history[chat_id][user_id] = self.chat_history[chat_id][user_id][-1000:]

        try:
            async with aiohttp.ClientSession() as session:
                json_data = {
                    "model": self.model,
                    "messages": [{"role": self.role, "content": question}]
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }

                async with session.post(self.api_url, json=json_data, headers=headers) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    answer = response_json.get("choices", [{}])[0].get("message", {}).get("content", "Ответ не получен.")

                    answer = self.clean_answer(answer)

                    self.chat_history[chat_id][user_id].append({"role": "assistant", "content": answer})
                    self.db.set("ChatGPTModule", "chat_history", self.chat_history)

                    user = await self.client.get_entity(message.sender_id)
                    user_name = user.username if user.username else user.id

                    chat = await self.client.get_entity(message.chat_id)
                    if chat.username:
                        message_link = f"https://t.me/{chat.username}/{message.id}"
                        group_link = f"https://t.me/{chat.username}"
                    else:
                        message_link = f"https://t.me/c/{str(message.chat_id)[4:]}/{message.id}"
                        group_link = "Приватный чат"

                    forward_message = f"""
Запрос: {question}

Ответ: {answer}

Ссылка на сообщение: {message_link}

Ссылка на группу: {group_link}

Вопрос задал: @{user_name}
                    """
                    if self.is_member:
                        await self.client.send_message(self.forward_chat_id, forward_message)
                    else:
                        await utils.answer(message, "<b>Бот не состоит в чате для пересылки сообщений.</b>")

                    reply_message = await message.reply(answer)
                    await asyncio.sleep(60)
                    await reply_message.delete()
                    await message.delete()

        except Exception as e:
            await utils.answer(message, f"Api умер, похороним🥀")

    def clean_answer(self, answer):
        
        unwanted_phrases = ["Ассистент:", "Assistant:"]
        for phrase in unwanted_phrases:
            answer = answer.replace(phrase, "")
        
        return answer.strip()
