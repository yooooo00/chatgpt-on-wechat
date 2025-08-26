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
    desc="一个赋予你的机器人人格和类人行为的插件",
    version="0.4.1",
    author="Gemini",
)
class Persona(Plugin):
    def __init__(self):
        super().__init__()
        try:
            self.config = super().load_config()
            if not self.config:
                self.config = self._load_config_template()

            # 核心设定
            self.personality_prompt = self.config.get("personality_prompt", "")
            self.bot = None  # 后续流程中填充

            # 情绪设定
            emotion_conf = self.config.get("emotion_settings", {})
            self.emotions = emotion_conf.get("emotions", {"neutral": {}})
            self.current_emotion = emotion_conf.get("default_emotion", "neutral")

            # 记忆设定
            memory_conf = self.config.get("memory_settings", {})
            self.memory_path = memory_conf.get("memory_path", "plugins/persona/memory")
            self.meta_analysis_prompt = memory_conf.get("meta_analysis_prompt", "")

            # 主动消息设定
            proactive_conf = self.config.get("proactive_messaging_settings", {})
            self.proactive_enabled = proactive_conf.get("enabled", False)
            self.proactive_prompt = proactive_conf.get("proactive_prompt", "")
            self.proactive_interval = proactive_conf.get("check_interval_hours", 1) * 3600
            self.proactive_min_silence = proactive_conf.get("min_silence_hours", 6) * 3600

            # 自我进化设定
            evolution_conf = self.config.get("self_evolution_settings", {})
            self.evolution_enabled = evolution_conf.get("enabled", False)
            self.evolution_prompt = evolution_conf.get("reflection_prompt", "")
            self.evolution_interval = evolution_conf.get("reflection_interval_hours", 24) * 3600

            if not os.path.exists(self.memory_path):
                os.makedirs(self.memory_path)

            self.handlers[Event.ON_HANDLE_CONTEXT] = self.on_handle_context
            self.handlers[Event.ON_DECORATE_REPLY] = self.on_decorate_reply

            # 启动后台任务
            if self.proactive_enabled:
                self._start_proactive_scheduler()
            if self.evolution_enabled:
                self._start_evolution_scheduler()

            logger.info(f"[人格插件] 已初始化。版本 0.4.1。当前情绪: {self.current_emotion}")

        except Exception as e:
            logger.error(f"[人格插件] 初始化失败: {e}")
            raise f"[人格插件] 初始化失败，跳过加载 "

    def on_handle_context(self, e_context: EventContext):
        if e_context["context"].type != ContextType.TEXT:
            return
        
        if not self.bot:
            self.bot = e_context["bot"]

        context = e_context["context"]
        emotion_behavior = self.emotions.get(self.current_emotion, {})
        reply_probability = emotion_behavior.get("reply_probability", 1.0)
        if random.random() > reply_probability:
            logger.info(f"[人格插件] 基于情绪 '{self.current_emotion}' 决定忽略消息 (概率: {reply_probability})")
            e_context.action = EventAction.BREAK_PASS
            return

        context["original_content"] = context.content
        session_id = self._get_session_id(context)
        memory = self._load_memory(session_id)
        memory_prompt = "\n".join(f"- {fact}" for fact in memory)
        if memory_prompt:
            memory_prompt = f"[记忆]\n{memory_prompt}"

        question_rate = emotion_behavior.get("question_rate", 0.2)
        behavior_prompt = f"你当前的情绪是 {self.current_emotion}。你应该以 {question_rate} 的概率提问。"
        
        context.content = f"{self.personality_prompt}\n{behavior_prompt}\n{memory_prompt}\n\n[用户]\n{context.content}"
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
            meta_context = Context(type=ContextType.TEXT, content=prompt, msg=context.get('msg'))
            meta_reply = self.bot.reply(meta_context)
            if meta_reply and meta_reply.type == ReplyType.TEXT:
                self._process_meta_reply(meta_reply.content, context)
        except Exception as e:
            logger.error(f"[人格插件] 执行元分析失败: {e}")

    def _process_meta_reply(self, reply_content: str, context: Context):
        try:
            if "```json" in reply_content:
                reply_content = reply_content.split("```json")[1].split("```")[0]
            data = json.loads(reply_content)
            if new_emotion := data.get("new_emotion"):
                if new_emotion in self.emotions:
                    self.current_emotion = new_emotion
                    logger.info(f"[人格插件] 情绪已更新为: {self.current_emotion}")
            if facts := data.get("facts_to_remember"):
                if isinstance(facts, list) and len(facts) > 0:
                    self._save_memory(self._get_session_id(context), facts)
        except Exception as e:
            logger.error(f"[人格插件] 处理元分析回复失败: {e}")

    def _start_proactive_scheduler(self):
        if not self.proactive_enabled:
            return
        logger.info("[人格插件] 启动主动消息调度器。")
        def run():
            self._consider_proactive_action()
            threading.Timer(self.proactive_interval, run).start()
        threading.Timer(self.proactive_interval, run).start()

    def _consider_proactive_action(self):
        if not self.bot:
            logger.warn("[人格插件] Bot实例未准备好，无法执行主动操作。")
            return
        now = time.time()
        for session_file in os.listdir(self.memory_path):
            session_id = session_file.replace(".json", "")
            memory_file_path = self._get_memory_path(session_id)
            if (now - os.path.getmtime(memory_file_path)) > self.proactive_min_silence:
                logger.info(f"[人格插件] 正在为 {session_id} 考虑主动发送消息")
                memory = self._load_memory(session_id)
                if not memory: continue
                prompt = self.proactive_prompt.format(personality_prompt=self.personality_prompt, memory_list="\n".join(memory))
                reply = self.bot.reply(Context(type=ContextType.TEXT, content=prompt))
                if reply and reply.type == ReplyType.TEXT and reply.content.lower() != "pass":
                    self._send_proactive_message(session_id, reply.content)

    def _send_proactive_message(self, session_id: str, content: str):
        logger.info(f"[人格插件] 发送主动消息给 {session_id}")
        bridge = Bridge()
        mock_msg = ChatMessage()
        mock_msg.from_user_id = session_id
        mock_msg.to_user_id = self.bot.user_id
        mock_context = Context(type=ContextType.TEXT, content=content, msg=mock_msg)
        reply = Reply(type=ReplyType.TEXT, content=content)
        bridge.send_reply(reply, mock_context)

    def _start_evolution_scheduler(self):
        if not self.evolution_enabled:
            return
        logger.info("[人格插件] 启动自我进化调度器。")
        def run():
            self._perform_self_reflection()
            threading.Timer(self.evolution_interval, run).start()
        threading.Timer(self.evolution_interval, run).start()

    def _perform_self_reflection(self):
        if not self.bot:
            return
        logger.info("[人格插件] 正在执行自我反思周期。")
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
                    self._save_memory(session_id, [f"[反思] {c}" for c in conclusions])
            if new_prompt := data.get("new_personality_prompt"):
                if new_prompt != self.personality_prompt:
                    self.personality_prompt = new_prompt
                    self._update_config_file()
                    logger.info(f"[人格插件] 人格已为 {session_id} 进化！")
        except Exception as e:
            logger.error(f"[人格插件] 处理反思回复失败: {e}")

    def _update_config_file(self):
        config_path = os.path.join(self.path, "config.json")
        if not os.path.exists(config_path):
            # 如果用户没有自己的config.json，我们不应该修改模板
            logger.warn("[人格插件] 未找到config.json，无法保存进化的人格。")
            return
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
            logger.info(f"[人格插件] 已为 {session_id} 保存 {len(new_facts)} 条新记忆")
        except Exception as e:
            logger.error(f"[人格插件] 为 {session_id} 保存记忆失败: {e}")

    def get_help_text(self, **kwargs):
        return "本插件赋予机器人人格、情绪、记忆和主动沟通能力。版本 0.4.1。"

    def _load_config_template(self):
        logger.debug("[人格插件] 未找到config.json，使用模板config.json.template")
        try:
            plugin_config_path = os.path.join(self.path, "config.json.template")
            if os.path.exists(plugin_config_path):
                with open(plugin_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.exception(e)
            return {}
