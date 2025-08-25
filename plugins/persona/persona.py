# encoding:utf-8

import json
import os
import random
import time

import plugins
from bridge.context import ContextType
from bridge.reply import Reply
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin


@plugins.register(
    name="Persona",
    desire_priority=99,
    hidden=False,
    desc="A plugin to give your bot a personality and human-like behavior",
    version="0.1",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            '''# encoding:utf-8

import json
import os
import random
import time

import plugins
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from common.log import logger
from plugins import Event, EventAction, EventContext, Plugin


@plugins.register(
    name="Persona",
    desire_priority=99,
    hidden=False,
    desc="A plugin to give your bot a personality and human-like behavior",
    version="0.2",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()

            # Persona settings
            self.personality_prompt = self.config.get("personality_prompt", "")
            
            # Delay settings
            self.reply_delay_min = self.config.get("reply_delay_seconds", {}).get("min", 1)
            self.reply_delay_max = self.config.get("reply_delay_seconds", {}).get("max", 5)

            # Emotion settings
            emotion_settings = self.config.get("emotion_settings", {})
            self.current_emotion = emotion_settings.get("default_emotion", "neutral")
            self.emotions = emotion_settings.get("emotions", ["neutral"])
            self.emotion_update_prompt = emotion_settings.get("emotion_update_prompt", "")

            if not self.personality_prompt:
                logger.warn("[Persona] Personality prompt is not set in config.")
            if not self.emotion_update_prompt:
                logger.warn("[Persona] Emotion update prompt is not set in config.")

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply
            logger.info(f"[Persona] inited, current emotion: {self.current_emotion}")
        except Exception as e:
            logger.error(f"[Persona] initialization failed: {e}")
            raise f"[Persona] init failed, ignore "

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return

        if not self.personality_prompt:
            return
        
        context = e_context["context"]
        # Store original content
        context["original_content"] = context.content

        logger.debug(f"[Persona] Current emotion: {self.current_emotion}")
        
        # Inject persona and emotion into prompt
        new_content = f"{self.personality_prompt}
[Current Emotion: {self.current_emotion}]
[user]
{context.content}"
        context.content = new_content
        e_context.action = EventAction.CONTINUE

    def on_decorate_reply(self, e_context: EventContext):
        if e_context["reply"].type != ReplyType.TEXT:
            return

        # Update emotion for next turn
        self._update_emotion(e_context)

        # Apply reply delay
        delay = random.uniform(self.reply_delay_min, self.reply_delay_max)
        logger.info(f"[Persona] Delaying reply for {delay:.2f} seconds")
        time.sleep(delay)

        e_context.action = EventAction.CONTINUE

    def _update_emotion(self, e_context: EventContext):
        if not self.emotion_update_prompt:
            return

        bot = e_context["bot"]
        if not bot:
            logger.warn("[Persona] Bot instance not found in context, skipping emotion update.")
            return

        try:
            user_message = e_context["context"].get("original_content", "")
            bot_reply = e_context["reply"].content
            
            # Format the meta-prompt for emotion analysis
            prompt = self.emotion_update_prompt.format(
                personality_prompt=self.personality_prompt,
                current_emotion=self.current_emotion,
                user_message=user_message,
                bot_reply=bot_reply,
                emotion_list=", ".join(self.emotions)
            )

            # Create a new context for the meta-call
            emotion_context = Context(type=ContextType.TEXT, content=prompt, msg=e_context['context']['msg'])
            
            logger.debug("[Persona] Requesting emotion update from LLM.")
            emotion_reply = bot.reply(emotion_context)
            
            if emotion_reply and emotion_reply.type == ReplyType.TEXT:
                new_emotion = emotion_reply.content.strip().lower()
                if new_emotion in self.emotions:
                    self.current_emotion = new_emotion
                    logger.info(f"[Persona] Emotion updated to: {self.current_emotion}")
                else:
                    logger.warn(f"[Persona] LLM returned an invalid emotion '{new_emotion}', keeping current emotion.")
            else:
                logger.warn("[Persona] Failed to get a valid reply for emotion update.")

        except Exception as e:
            logger.error(f"[Persona] Failed to update emotion: {e}")


    def get_help_text(self, **kwargs):
        return "This plugin gives your bot a personality and manages its emotions. Configure it in plugins/persona/config.json."

    def _load_config_template(self):
        logger.debug("No Persona plugin config.json, use plugins/persona/config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    plugin_conf = json.load(f)
                    return plugin_conf
        except Exception as e:
            logger.exception(e)
            return {}
''

