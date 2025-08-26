#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import time

# 设置项目路径以支持导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.context import ContextType
from channel.channel_factory import create_channel
from channel.terminal.terminal_channel import TerminalMessage
from common import const
from common.log import logger
from config import load_config
from plugins import load_plugins, plugins

def run_test():
    """主函数，用于运行人格插件测试。"""

    # 1. 设置环境
    logger.info("正在设置测试环境...")
    load_config()
    load_plugins()

    if "persona" not in plugins:
        logger.error("人格插件未加载。请检查 config.json。")
        return

    channel = create_channel("terminal")
    persona_plugin = plugins["persona"]
    test_user_id = "test_user_001"

    # 2. 定义对话脚本
    script = [
        ("user", "你好啊，你是谁？"),
        ("user", "我叫张三。我最近有点着迷于看诺兰的电影，特别是星际穿越，那种宏大的科幻感太棒了。"),
        ("user", "不说这个了，有点无聊。你今天心情怎么样？"),
        ("user", "你为什么回复这么慢？真没劲，我走了。"),
        # --- 模拟长时间的沉默 ---
        ("system", "PAUSE_12_HOURS"),
        ("user", "我昨天是不是有点暴躁？抱歉哈。"),
        ("user", "对了，你还记得我喜欢什么类型的电影吗？"),
    ]

    # 3. 运行对话
    logger.info("--- 开始模拟对话 ---")
    msg_id_counter = 0
    for speaker, content in script:
        if speaker == "system" and content.startswith("PAUSE"):
            hours = int(content.split("_")[1])
            logger.info(f"--- 模拟 {hours} 小时的时间间隔 ---")
            # 真实场景中我们无法暂停12小时，所以这里仅为演示
            # 在真实应用中，这期间主动消息调度器可能会触发
            # 为模拟此场景，我们手动触发一次主动行为检查
            persona_plugin._consider_proactive_action()
            time.sleep(5) # 等待机器人可能的响应
            continue

        logger.info(f"用户 ({test_user_id}): {content}")
        msg_id_counter += 1
        
        # 模拟channel的行为
        msg = TerminalMessage(
            msg_id=msg_id_counter,
            content=content,
            from_user_id=test_user_id,
            to_user_id="Chatgpt",
            other_user_id=test_user_id
        )
        context = channel._compose_context(ContextType.TEXT, content, msg=msg)
        context["isgroup"] = False
        
        channel.produce(context)
        time.sleep(15) # 等待机器人回复和人格插件处理

    logger.info("--- 对话结束 ---")

    # 4. 事后分析
    logger.info("--- 最终分析 ---")
    final_emotion = persona_plugin.current_emotion
    logger.info(f"[分析] 机器人最终情绪状态: {final_emotion}")

    memory_file_path = persona_plugin._get_memory_path(test_user_id)
    if os.path.exists(memory_file_path):
        logger.info(f"[分析] 正在读取记忆文件: {memory_file_path}")
        with open(memory_file_path, 'r', encoding='utf-8') as f:
            memory_data = json.load(f)
            logger.info("[分析] 最终记忆内容:")
            for fact in memory_data:
                logger.info(f"  - {fact}")
    else:
        logger.warn("[分析] 未找到该用户的记忆文件。")

if __name__ == "__main__":
    run_test()
