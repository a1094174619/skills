# Python 3.8 兼容性修复说明

## 概述

本次修改将技能目录中使用了 Python 3.9+ 语法特性的代码改为 Python 3.8 兼容写法，确保代码可以在 Windows 7 + Python 3.8 环境下正常运行。

---

## 修改清单

### 修改 1：comment.py

**文件路径：** `docx\scripts\comment.py`

**修改行号：** 第 99 行

**修改前：**
```python
def _find_para_id(comments_path: Path, comment_id: int) -> str | None:
```

**修改后：**
```python
def _find_para_id(comments_path: Path, comment_id: int) -> Optional[str]:
```

**修改说明：**
- `str | None` 是 Python 3.10 引入的联合类型语法
- 改为 `Optional[str]` 是 Python 3.8 兼容的写法
- 两者在运行时完全等效，仅语法不同
- 文件第 22 行已有 `from typing import Tuple, Optional` 导入，无需额外添加导入语句

---

### 修改 2：simplify_redlines.py

**文件路径：** `docx\scripts\office\helpers\simplify_redlines.py`

**修改行号：** 第 182 行

**修改前：**
```python
    new_changes: dict[str, int] = {}
```

**修改后：**
```python
    new_changes: Dict[str, int] = {}
```

**修改说明：**
- `dict[str, int]` 是 Python 3.9 引入的内置泛型语法
- 改为 `Dict[str, int]` 是 Python 3.8 兼容的写法
- 两者在运行时完全等效，仅语法不同
- 文件第 16 行已有 `from typing import Dict` 导入，无需额外添加导入语句

---

### 修改 3：pptx\validate.py

**文件路径：** `pptx\scripts\office\validate.py`

**修改行号：** 第 80-93 行

**修改前：**
```python
    match file_extension:
        case ".docx":
            validators = [
                DOCXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
            ]
            if original_file:
                validators.append(
                    RedliningValidator(unpacked_dir, original_file, verbose=args.verbose, author=args.author)  
                )
        case ".pptx":
            validators = [
                PPTXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
            ]
        case _:
            print(f"Error: Validation not supported for file type {file_extension}")
            sys.exit(1)
```

**修改后：**
```python
    if file_extension == ".docx":
        validators = [
            DOCXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
        ]
        if original_file:
            validators.append(
                RedliningValidator(unpacked_dir, original_file, verbose=args.verbose, author=args.author)  
            )
    elif file_extension == ".pptx":
        validators = [
            PPTXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
        ]
    else:
        print(f"Error: Validation not supported for file type {file_extension}")
        sys.exit(1)
```

**修改说明：**
- `match/case` 是 Python 3.10 引入的结构化模式匹配语法
- 改为 `if/elif/else` 是 Python 3.8 兼容的写法
- 两者逻辑完全等效，仅语法不同

---

### 修改 4：xlsx\validate.py

**文件路径：** `xlsx\scripts\office\validate.py`

**修改行号：** 第 80-93 行

**修改前：**
```python
    match file_extension:
        case ".docx":
            validators = [
                DOCXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
            ]
            if original_file:
                validators.append(
                    RedliningValidator(unpacked_dir, original_file, verbose=args.verbose, author=args.author)  
                )
        case ".pptx":
            validators = [
                PPTXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
            ]
        case _:
            print(f"Error: Validation not supported for file type {file_extension}")
            sys.exit(1)
```

**修改后：**
```python
    if file_extension == ".docx":
        validators = [
            DOCXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
        ]
        if original_file:
            validators.append(
                RedliningValidator(unpacked_dir, original_file, verbose=args.verbose, author=args.author)  
            )
    elif file_extension == ".pptx":
        validators = [
            PPTXSchemaValidator(unpacked_dir, original_file, verbose=args.verbose),
        ]
    else:
        print(f"Error: Validation not supported for file type {file_extension}")
        sys.exit(1)
```

**修改说明：**
- `match/case` 是 Python 3.10 引入的结构化模式匹配语法
- 改为 `if/elif/else` 是 Python 3.8 兼容的写法
- 两者逻辑完全等效，仅语法不同

---

## 验证方法

修改完成后，可通过以下方式验证代码是否正确：

```bash
# 语法检查
python -m py_compile docx\scripts\comment.py
python -m py_compile docx\scripts\office\helpers\simplify_redlines.py
python -m py_compile pptx\scripts\office\validate.py
python -m py_compile xlsx\scripts\office\validate.py
```

---

## 注意事项

1. 类型注解修改（修改 1、2）仅涉及**类型注解**，不影响代码的运行逻辑
2. 控制流修改（修改 3、4）将 `match/case` 改为 `if/elif/else`，逻辑完全等效
3. 类型注解在 Python 运行时会被忽略，仅用于静态类型检查和 IDE 提示
4. 修改后的代码与修改前功能完全一致
5. 确保修改时保持缩进一致（注意空格和制表符）

---

## 技术背景

| 语法特性 | 引入版本 | Python 3.8 兼容写法 |
|---------|---------|-------------------|
| `str \| None` | Python 3.10 | `Optional[str]` |
| `dict[str, int]` | Python 3.9 | `Dict[str, int]` |
| `list[str]` | Python 3.9 | `List[str]` |
| `set[str]` | Python 3.9 | `Set[str]` |
| `tuple[str, int]` | Python 3.9 | `Tuple[str, int]` |
| `match/case` | Python 3.10 | `if/elif/else` |

---

*文档生成时间：2026-04-12*
