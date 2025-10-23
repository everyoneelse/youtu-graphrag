# 修复 UnicodeDecodeError 错误

## 🔍 错误原因

`UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80 in position 0`

这个错误通常发生在：
1. **尝试以文本模式打开 Pickle 文件** - Pickle 是二进制格式
2. **文件编码不是 UTF-8** - 某些系统生成的文件可能是其他编码
3. **文件损坏** - 文件内容被破坏

## ⚡ 快速修复

### 问题1: 打开 Pickle 文件错误

**❌ 错误的方式：**
```python
# 这会导致 UnicodeDecodeError
with open('semantic_results.pkl', 'r') as f:  # ❌ 错误！
    data = pickle.load(f)
```

**✅ 正确的方式：**
```python
# 必须使用 'rb' 模式
with open('semantic_results.pkl', 'rb') as f:  # ✅ 正确！
    data = pickle.load(f)
```

### 问题2: JSON 文件编码问题

如果你的中间结果 JSON 文件有编码问题：

**尝试1: 指定 UTF-8 编码**
```python
with open('intermediate.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
```

**尝试2: 使用 latin-1 编码（兼容性更好）**
```python
with open('intermediate.json', 'r', encoding='latin-1') as f:
    data = json.load(f)
```

**尝试3: 忽略错误**
```python
with open('intermediate.json', 'r', encoding='utf-8', errors='ignore') as f:
    data = json.load(f)
```

## 🛠️ 诊断你的文件

运行诊断脚本：
```bash
# 诊断特定文件
python3 diagnose_encoding_error.py your_file.json

# 或
python3 diagnose_encoding_error.py your_file.pkl
```

## 📝 具体场景修复

### 场景1: 运行 restore_semantic_results.py 时出错

如果错误发生在这个脚本中，检查你的输入文件：

```bash
# 检查文件编码
file output/dedup_intermediate/your_file.json

# 使用诊断工具
python3 diagnose_encoding_error.py output/dedup_intermediate/your_file.json
```

如果文件编码有问题，可以转换编码：
```bash
# 转换为 UTF-8
iconv -f GBK -t UTF-8 input.json > output.json
```

### 场景2: 在代码中加载 Pickle 文件时出错

**检查代码中的文件打开方式：**

```python
# ❌ 错误
with open('file.pkl', 'r') as f:

# ✅ 正确
with open('file.pkl', 'rb') as f:
```

### 场景3: 在 kt_gen.py 中使用缓存时出错

如果你已经修改了 `kt_gen.py` 来使用缓存，确保：

```python
# 在 kt_gen.py 中加载缓存时
if self.cached_semantic_results:
    import pickle
    with open(self.cached_semantic_results, 'rb') as f:  # ✅ 必须是 'rb'
        semantic_results = pickle.load(f)
```

## 🔧 修复后的脚本

我已经检查了所有脚本，它们都正确使用了编码。但如果你遇到问题，这里是关键部分的正确写法：

### restore_semantic_results.py 中的正确写法

```python
# 读取 JSON（输入）
with open(intermediate_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 保存 Pickle（输出）
with open(output_file, 'wb') as f:  # 注意 'wb'
    pickle.dump(semantic_results, f)

# 保存 JSON（输出）
with open(json_output, 'w', encoding='utf-8') as f:
    json.dump(semantic_results, f, indent=2, ensure_ascii=False)
```

### 使用缓存时的正确写法

```python
# 加载 Pickle 缓存
with open('cached_results.pkl', 'rb') as f:  # 必须 'rb'
    semantic_results = pickle.load(f)
```

## 🐛 调试步骤

如果错误仍然存在：

### 1. 找到出错的具体位置

运行时添加 `-v` 或查看完整的错误堆栈：
```bash
python3 -v restore_semantic_results.py your_file.json 2>&1 | tee error.log
```

### 2. 检查文件

```bash
# 查看文件类型
file your_file.json

# 查看文件头
hexdump -C your_file.json | head

# 检查编码
python3 -c "
import chardet
with open('your_file.json', 'rb') as f:
    result = chardet.detect(f.read())
    print(result)
"
```

### 3. 尝试修复文件

如果文件编码确实有问题：

```python
# 方法1: 读取为二进制再解码
with open('input.json', 'rb') as f:
    content = f.read()
    # 尝试不同编码
    try:
        text = content.decode('utf-8')
    except:
        text = content.decode('latin-1')

# 重新保存为 UTF-8
with open('output.json', 'w', encoding='utf-8') as f:
    f.write(text)
```

## 📞 仍然有问题？

如果以上方法都不能解决，请提供：

1. **完整的错误信息**（包括堆栈跟踪）
   ```bash
   python3 your_script.py 2>&1 | tee error.log
   ```

2. **你执行的命令**
   ```bash
   # 例如
   python3 restore_semantic_results.py output/dedup_intermediate/xxx.json
   ```

3. **文件信息**
   ```bash
   file your_file.json
   ls -lh your_file.json
   head -c 100 your_file.json | hexdump -C
   ```

## ✅ 验证修复

修复后，运行测试确认：

```bash
# 运行完整测试
python3 test_restore_semantic_results.py

# 或手动测试
python3 -c "
import pickle
with open('your_file.pkl', 'rb') as f:
    data = pickle.load(f)
    print('✅ 成功加载！')
    print(f'数据类型: {type(data)}')
"
```
