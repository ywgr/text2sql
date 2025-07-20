#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量修复Unicode字符的脚本
"""

import os
import re

def fix_unicode_in_file(filepath):
    """修复文件中的Unicode字符"""
    if not os.path.exists(filepath):
        return False
    
    # Unicode字符映射
    unicode_map = {
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARNING]',
        '🎉': '[SUCCESS]',
        '📁': '[FOLDER]',
        '🔧': '[CONFIG]',
        '🧪': '[TEST]',
        '📦': '[PACKAGE]',
        '🚀': '[START]',
        '🏠': '[HOME]',
        '🔍': '[SEARCH]',
        '🤖': '[AI]',
        '🗄️': '[DATABASE]',
        '🐍': '[PYTHON]',
        '🌐': '[WEB]',
        '📱': '[MOBILE]',
        '⏹️': '[STOP]',
        '👋': '[BYE]',
        '💡': '[IDEA]',
        '📊': '[CHART]',
        '🔄': '[LOADING]',
        '💻': '[COMPUTER]',
        '📈': '[TREND]',
        '🔒': '[SECURE]',
        '📝': '[NOTE]',
        '🎯': '[TARGET]',
        '⭐': '[STAR]',
        '🔥': '[HOT]',
        '💪': '[STRONG]',
        '🎨': '[ART]',
        '📚': '[BOOK]',
        '🌟': '[SHINE]',
        '💎': '[DIAMOND]',
        '🚪': '[DOOR]',
        '🔑': '[KEY]',
        '🎪': '[CIRCUS]',
        '🎭': '[MASK]',
        '🎬': '[MOVIE]',
        '🎵': '[MUSIC]',
        '🎸': '[GUITAR]',
        '🎤': '[MIC]',
        '🎧': '[HEADPHONE]',
        '🎮': '[GAME]',
        '🎲': '[DICE]',
        '🎯': '[DART]',
        '🎪': '[TENT]',
        '🎨': '[PALETTE]',
        '🎭': '[THEATER]',
        '🎬': '[CINEMA]',
        '🎵': '[NOTE]',
        '🎶': '[NOTES]',
        '🎼': '[SCORE]',
        '🎹': '[PIANO]',
        '🥁': '[DRUM]',
        '🎺': '[TRUMPET]',
        '🎻': '[VIOLIN]',
        '🎸': '[GUITAR]',
        '🎤': '[MICROPHONE]',
        '🎧': '[HEADPHONES]',
        '📻': '[RADIO]',
        '📺': '[TV]',
        '📷': '[CAMERA]',
        '📹': '[VIDEO]',
        '📼': '[TAPE]',
        '💿': '[CD]',
        '📀': '[DVD]',
        '💽': '[DISK]',
        '💾': '[FLOPPY]',
        '💻': '[LAPTOP]',
        '🖥️': '[DESKTOP]',
        '🖨️': '[PRINTER]',
        '⌨️': '[KEYBOARD]',
        '🖱️': '[MOUSE]',
        '🖲️': '[TRACKBALL]',
        '💡': '[BULB]',
        '🔦': '[FLASHLIGHT]',
        '🕯️': '[CANDLE]',
        '🪔': '[LAMP]',
        '🔥': '[FIRE]',
        '💥': '[EXPLOSION]',
        '💫': '[DIZZY]',
        '💨': '[WIND]',
        '💧': '[DROP]',
        '💦': '[SWEAT]',
        '☔': '[RAIN]',
        '⛈️': '[STORM]',
        '🌈': '[RAINBOW]',
        '☀️': '[SUN]',
        '🌙': '[MOON]',
        '⭐': '[STAR]',
        '🌟': '[GLOWING_STAR]',
        '✨': '[SPARKLES]',
        '⚡': '[LIGHTNING]',
        '🔥': '[FLAME]',
        '💥': '[BOOM]',
        '💫': '[STAR_STRUCK]',
        '💨': '[DASH]',
        '💧': '[DROPLET]',
        '💦': '[SWEAT_DROPLETS]',
        '☔': '[UMBRELLA_RAIN]',
        '⛈️': '[CLOUD_LIGHTNING]',
        '🌈': '[RAINBOW]',
        '☀️': '[SUN]',
        '🌙': '[CRESCENT_MOON]'
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换Unicode字符
        for unicode_char, replacement in unicode_map.items():
            content = content.replace(unicode_char, replacement)
        
        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"已修复文件: {filepath}")
        return True
        
    except Exception as e:
        print(f"修复文件失败 {filepath}: {e}")
        return False

def main():
    """主函数"""
    print("批量修复Unicode字符...")
    
    # 需要修复的文件列表
    files_to_fix = [
        'setup_local_environment.py',
        'quick_start.py',
        'test_local_system.py',
        'run_local_system.py',
        'text2sql_local_deepseek.py'
    ]
    
    fixed_count = 0
    
    for filepath in files_to_fix:
        if fix_unicode_in_file(filepath):
            fixed_count += 1
    
    print(f"修复完成: {fixed_count}/{len(files_to_fix)} 个文件")
    print("现在可以运行: python quick_start.py")

if __name__ == "__main__":
    main()