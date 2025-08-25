# encoding:utf-8

import json
import os
import random
import threading
import time

import plugins
from bridge.bridge import Bridge
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from channel.chat_message import ChatMessage
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin


@plugins.register(
    name="Persona",
    desire_priority=99,
    hidden=False,
    desc="A plugin to give your bot a personality and human-like behavior",
    version="0.4",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()

            # Core settings
            self.personality_prompt = self.config.get("personality_prompt", "")
            self.bot = None  # To be populated later

            # Emotion settings
            emotion_conf = self.config.get("emotion_settings", {})
            self.emotions = emotion_conf.get("emotions", {"neutral": {}})
            self.current_emotion = emotion_conf.get("default_emotion", "neutral")

            # Memory settings
            memory_conf = self.config.get("memory_settings", {})
            self.memory_path = memory_conf.get("memory_path", "plugins/persona/memory")
            self.meta_analysis_prompt = memory_conf.get("meta_analysis_prompt", "")

            # Proactive messaging settings
            proactive_conf = self.config.get("proactive_messaging_settings", {})
            self.proactive_enabled = proactive_conf.get("enabled", False)
            self.proactive_prompt = proactive_conf.get("proactive_prompt", "")
            self.proactive_interval = proactive_conf.get("check_interval_hours", 1) * 3600
            self.proactive_min_silence = proactive_conf.get("min_silence_hours", 6) * 3600

            # Self-evolution settings
            evolution_conf = self.config.get("self_evolution_settings", {})
            self.evolution_enabled = evolution_conf.get("enabled", False)
            self.evolution_prompt = evolution_conf.get("reflection_prompt", "")
            self.evolution_interval = evolution_conf.get("reflection_interval_hours", 24) * 3600

            if not os.path.exists(self.memory_path):
                os.makedirs(self.memory_path)

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply

            # Start background tasks
            if self.proactive_enabled:
                self._start_proactive_scheduler()
            if self.evolution_enabled:
                self._start_evolution_scheduler()

            logger.info(f"[Persona] inited. Version 0.4. Emotion: {self.current_emotion}")

        except Exception as e:
            logger.error(f"[Persona] initialization failed: {e}")
            raise f"[Persona] init failed, ignore "

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        
        if not self.bot:
            self.bot = e_context["bot"]

        context = e_context["context"]
        emotion_behavior = self.emotions.get(self.current_emotion, {})
        reply_probability = emotion_behavior.get("reply_probability", 1.0)
        if random.random() > reply_probability:
            logger.info(f"[Persona] Ignoring message based on emotion '{self.current_emotion}'")
            e_context.action = EventAction.BREAK_PASS
            return

        context["original_content"] = context.content
        session_id = self._get_session_id(context)
        memory = self._load_memory(session_id)
        memory_prompt = "\n".join(f"- {fact}" for fact in memory)
        if memory_prompt:
            memory_prompt = f"[Memory]\n{memory_prompt}"

        question_rate = emotion_behavior.get("question_rate", 0.2)
        behavior_prompt = f"Your current emotion is {self.current_emotion}. You should ask questions with a probability of {question_rate}."
        
        context.content = f"{self.personality_prompt}\n{behavior_prompt}\n{memory_prompt}\n\n[user]\n{context.content}"
        e_context.action = EventAction.CONTINUE

    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type != ReplyType.TEXT:
            return
        self._perform_meta_analysis(e_context)

    def _perform_meta_analysis(self, e_context: EventContext):
        if not self.meta_analysis_prompt or not self.bot:
            return
        try:
            context = e_context["context"]
            prompt = self.meta_analysis_prompt.format(
                personality_prompt=self.personality_prompt,
                current_emotion=self.current_emotion,
                user_message=context.get("original_content", ""),
                bot_reply=e_context["reply"].content,
                emotion_list=", ".join(self.emotions.keys())
            )
            meta_context = Context(type=ContextType.TEXT, content=prompt, msg=context['msg'])
            meta_reply = self.bot.reply(meta_context)
            if meta_reply and meta_reply.type == ReplyType.TEXT:
                self._process_meta_reply(meta_reply.content, context)
        except Exception as e:
            logger.error(f"[Persona] Failed to perform meta-analysis: {e}")

    def _process_meta_reply(self, reply_content: str, context: Context):
        try:
            if "```json" in reply_content:
                reply_content = reply_content.split("```json")[1].split("```")[0]
            data = json.loads(reply_content)
            if new_emotion := data.get("new_emotion"):
                if new_emotion in self.emotions:
                    self.current_emotion = new_emotion
                    logger.info(f"[Persona] Emotion updated to: {self.current_emotion}")
            if facts := data.get("facts_to_remember"):
                if isinstance(facts, list) and len(facts) > 0:
                    self._save_memory(self._get_session_id(context), facts)
        except Exception as e:
            logger.error(f"[Persona] Error processing meta-analysis reply: {e}")

    def _start_proactive_scheduler(self):
        if not self.proactive_enabled:
            return
        logger.info("[Persona] Starting proactive messaging scheduler.")
        def run():
            self._consider_proactive_action()
            threading.Timer(self.proactive_interval, run).start()
        threading.Timer(self.proactive_interval, run).start()

    def _consider_proactive_action(self):
        if not self.bot:
            return
        now = time.time()
        for session_file in os.listdir(self.memory_path):
            session_id = session_file.replace(".json", "")
            memory_file_path = self._get_memory_path(session_id)
            if (now - os.path.getmtime(memory_file_path)) > self.proactive_min_silence:
                logger.info(f"[Persona] Considering proactive message for {session_id}")
                memory = self._load_memory(session_id)
                if not memory: continue
                prompt = self.proactive_prompt.format(personality_prompt=self.personality_prompt, memory_list="\n".join(memory))
                reply = self.bot.reply(Context(type=ContextType.TEXT, content=prompt))
                if reply and reply.type == ReplyType.TEXT and reply.content.lower() != "pass":
                    self._send_proactive_message(session_id, reply.content)

    def _send_proactive_message(self, session_id: str, content: str):
        logger.info(f"[Persona] Sending proactive message to {session_id}")
        bridge = Bridge()
        # This part is tricky as it depends on the exact channel implementation
        # We construct a mock context to deliver the message
        # This might need adjustment based on the project's architecture
        mock_msg = ChatMessage()
        mock_msg.from_user_id = session_id
        mock_msg.to_user_id = self.bot.user_id # Assuming bot has user_id
        mock_context = Context(type=ContextType.TEXT, content=content, msg=mock_msg)
        reply = Reply(type=ReplyType.TEXT, content=content)
        bridge.send_reply(reply, mock_context)

    def _start_evolution_scheduler(self):
        if not self.evolution_enabled:
            return
        logger.info("[Persona] Starting self-evolution scheduler.")
        def run():
            self._perform_self_reflection()
            threading.Timer(self.evolution_interval, run).start()
        threading.Timer(self.evolution_interval, run).start()

    def _perform_self_reflection(self):
        if not self.bot:
            return
        logger.info("[Persona] Performing self-reflection cycle.")
        for session_file in os.listdir(self.memory_path):
            session_id = session_file.replace(".json", "")
            memory = self._load_memory(session_id)
            if not memory: continue
            prompt = self.evolution_prompt.format(personality_prompt=self.personality_prompt, memory_list="\n".join(memory))
            reply = self.bot.reply(Context(type=ContextType.TEXT, content=prompt))
            if reply and reply.type == ReplyType.TEXT:
                self._process_reflection_reply(reply.content, session_id)

    def _process_reflection_reply(self, reply_content: str, session_id: str):
        try:
            if "```json" in reply_content:
                reply_content = reply_content.split("```json")[1].split("```")[0]
            data = json.loads(reply_content)
            if conclusions := data.get("conclusions"):
                if isinstance(conclusions, list) and len(conclusions) > 0:
                    self._save_memory(session_id, [f"[Reflection] {c}" for c in conclusions])
            if new_prompt := data.get("new_personality_prompt"):
                if new_prompt != self.personality_prompt:
                    self.personality_prompt = new_prompt
                    self._update_config_file()
                    logger.info(f"[Persona] Personality has evolved for {session_id}!")
        except Exception as e:
            logger.error(f"[Persona] Error processing reflection reply: {e}")

    def _update_config_file(self):
        config_path = os.path.join(self.path, "config.json")
        if not os.path.exists(config_path):
            config_path = os.path.join(self.path, "config.json.template")
        with open(config_path, 'r+', encoding='utf-8') as f:
            config_data = json.load(f)
            config_data['personality_prompt'] = self.personality_prompt
            f.seek(0)
            json.dump(config_data, f, ensure_ascii=False, indent=4)
            f.truncate()

    def _get_session_id(self, context: Context) -> str:
        return context["session_id"]

    def _get_memory_path(self, session_id: str) -> str:
        return os.path.join(self.memory_path, f"{session_id}.json")

    def _load_memory(self, session_id: str) -> list:
        memory_file = self._get_memory_path(session_id)
        if not os.path.exists(memory_file): return []
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: return []

    def _save_memory(self, session_id: str, new_facts: list):
        memory_file = self._get_memory_path(session_id)
        memory = self._load_memory(session_id)
        memory.extend(new_facts)
        try:
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=4)
            logger.info(f"[Persona] Saved {len(new_facts)} new facts to memory for {session_id}")
        except Exception as e:
            logger.error(f"[Persona] Failed to save memory for {session_id}: {e}")

    def get_help_text(self, **kwargs):
        return "This plugin gives your bot a personality, emotions, memory, and proactive capabilities. Version 0.4."

    def _load_config_template(self):
        logger.debug("No Persona plugin config.json, use plugins/persona/config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.exception(e)
            return {}
