#!/usr/bin/env python3
"""
诊断和修复 UnicodeDecodeError 的脚本
"""

import os
import sys
import pickle
import json


def diagnose_file(filepath):
    """诊断文件的编码问题"""
    
    print(f"\n{'='*70}")
    print(f"诊断文件: {filepath}")
    print(f"{'='*70}")
    
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return False
    
    # 检查文件大小
    size = os.path.getsize(filepath)
    print(f"文件大小: {size} bytes")
    
    # 检查文件头（前几个字节）
    with open(filepath, 'rb') as f:
        header = f.read(min(20, size))
        print(f"文件头（十六进制）: {header.hex()}")
        print(f"文件头（ASCII尝试）: {header[:20]}")
    
    # 判断文件类型
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.pkl':
        print(f"\n✅ 这是一个 Pickle 文件（二进制格式）")
        print(f"正确的打开方式：")
        print(f"  import pickle")
        print(f"  with open('{filepath}', 'rb') as f:  # 注意 'rb' 模式")
        print(f"      data = pickle.load(f)")
        
        # 尝试加载
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            print(f"\n✅ Pickle 文件可以正常加载")
            print(f"数据类型: {type(data)}")
            if isinstance(data, list):
                print(f"列表长度: {len(data)}")
            return True
        except Exception as e:
            print(f"\n❌ Pickle 文件加载失败: {e}")
            return False
    
    elif ext == '.json':
        print(f"\n✅ 这是一个 JSON 文件（文本格式）")
        
        # 尝试不同的编码
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'gbk', 'gb2312']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    data = json.load(f)
                print(f"\n✅ 使用 {encoding} 编码成功读取")
                return True
            except UnicodeDecodeError:
                print(f"❌ {encoding} 编码失败")
            except json.JSONDecodeError as e:
                print(f"⚠️  {encoding} 可以读取，但JSON格式错误: {e}")
                return False
        
        print(f"\n❌ 所有编码都失败")
        return False
    
    else:
        print(f"\n⚠️  未知文件类型: {ext}")
        return False


def fix_restore_script():
    """检查并修复 restore_semantic_results.py 脚本"""
    
    script_path = "restore_semantic_results.py"
    
    print(f"\n{'='*70}")
    print(f"检查脚本: {script_path}")
    print(f"{'='*70}")
    
    if not os.path.exists(script_path):
        print(f"❌ 脚本不存在")
        return
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查常见问题
    issues = []
    
    # 检查是否正确使用 'rb' 模式读取 pickle
    if "open(" in content and "'rb'" not in content and '"rb"' not in content:
        if ".pkl" in content:
            issues.append("⚠️  脚本可能没有使用 'rb' 模式读取 pickle 文件")
    
    # 检查是否指定了 encoding
    if "open(" in content and "encoding=" not in content:
        issues.append("⚠️  部分 open() 调用可能没有指定 encoding 参数")
    
    if issues:
        print("发现潜在问题：")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ 脚本看起来没有明显问题")


def provide_fix_examples():
    """提供修复示例"""
    
    print(f"\n{'='*70}")
    print(f"常见错误和修复方法")
    print(f"{'='*70}")
    
    print("\n❌ 错误的方式（会导致 UnicodeDecodeError）：")
    print("```python")
    print("# 错误：用文本模式打开 pickle 文件")
    print("with open('file.pkl', 'r') as f:  # ❌ 错误")
    print("    data = pickle.load(f)")
    print("")
    print("# 错误：没有指定编码")
    print("with open('file.json', 'r') as f:  # ⚠️  可能有问题")
    print("    data = json.load(f)")
    print("```")
    
    print("\n✅ 正确的方式：")
    print("```python")
    print("# 正确：pickle 文件用二进制模式")
    print("with open('file.pkl', 'rb') as f:  # ✅ 正确")
    print("    data = pickle.load(f)")
    print("")
    print("# 正确：JSON 文件明确指定编码")
    print("with open('file.json', 'r', encoding='utf-8') as f:  # ✅ 正确")
    print("    data = json.load(f)")
    print("```")


def main():
    print("="*70)
    print("UnicodeDecodeError 诊断和修复工具")
    print("="*70)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        # 诊断指定的文件
        for filepath in sys.argv[1:]:
            diagnose_file(filepath)
    else:
        print("\n没有指定文件，执行常规检查...")
        
        # 检查常见的文件
        common_files = [
            "output/dedup_intermediate/test_semantic_results_mock.pkl",
            "output/dedup_intermediate/test_semantic_results_mock.json",
            "output/dedup_intermediate/test_edge_dedup_mock.json",
        ]
        
        found_files = []
        for f in common_files:
            if os.path.exists(f):
                found_files.append(f)
        
        if found_files:
            print(f"\n找到 {len(found_files)} 个测试文件:")
            for f in found_files:
                diagnose_file(f)
        else:
            print("\n⚠️  没有找到测试文件")
            print("请指定要诊断的文件：")
            print(f"  python3 {sys.argv[0]} <file_path>")
    
    # 检查脚本
    fix_restore_script()
    
    # 提供修复示例
    provide_fix_examples()
    
    print(f"\n{'='*70}")
    print("诊断完成")
    print(f"{'='*70}")
    
    print("\n💡 如果问题仍然存在，请提供：")
    print("  1. 完整的错误信息（包括堆栈跟踪）")
    print("  2. 你执行的命令")
    print("  3. 出问题的文件路径")


if __name__ == "__main__":
    main()
