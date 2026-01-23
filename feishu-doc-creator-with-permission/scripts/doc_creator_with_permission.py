#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档创建器+权限管理器 - 合并子技能
在飞书创建文档并自动完成权限管理
输出：doc_with_permission.json
"""

import sys
import json
import urllib.parse
import time
from pathlib import Path
from datetime import datetime
import requests

# 添加 feishu_auth 路径
AUTH_SCRIPT_DIR = Path(__file__).parent.parent.parent / "feishu-doc-creator" / "scripts"
if str(AUTH_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUTH_SCRIPT_DIR))


def load_config():
    """加载飞书配置"""
    config_path = Path(__file__).parent.parent.parent.parent / "feishu-config.env"
    if not config_path.exists():
        config_path = Path(".claude/feishu-config.env")

    config = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip().strip('"\'')
    return config


def get_access_token(config, use_user_token=False):
    """获取访问令牌"""
    if use_user_token:
        # 从文件读取 user_access_token
        token_path = Path(__file__).parent.parent.parent.parent / "feishu-token.json"
        if token_path.exists():
            with open(token_path, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
                # 支持 access_token 和 user_access_token 两种格式
                return token_data.get("user_access_token") or token_data.get("access_token")
        return None
    else:
        # 获取 tenant_access_token
        url = f"{config['FEISHU_API_DOMAIN']}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        payload = {
            "app_id": config['FEISHU_APP_ID'],
            "app_secret": config['FEISHU_APP_SECRET']
        }
        response = requests.post(url, json=payload, headers=headers)
        result = response.json()
        if result.get("code") == 0:
            return result["tenant_access_token"]
        else:
            raise Exception(f"获取 tenant_access_token 失败: {result}")


def create_document(token, config, title):
    """创建飞书文档"""
    url = f"{config['FEISHU_API_DOMAIN']}/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "title": title,
        "folder_token": config.get('FEISHU_DEFAULT_FOLDER', '')
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()

    if result.get("code") == 0:
        return result["data"]["document"]["document_id"]
    else:
        raise Exception(f"创建文档失败: {result}")


def add_permission_member(token, config, document_id, user_id, user_type, perm):
    """添加协作者权限 - 必须使用 tenant_access_token"""
    params = urllib.parse.urlencode({"type": "docx"})
    url = f"{config['FEISHU_API_DOMAIN']}/open-apis/drive/v1/permissions/{document_id}/members?{params}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "member_id": user_id,
        "member_type": user_type,
        "perm": perm
    }

    response = requests.post(url, json=payload, headers=headers)
    result = response.json()

    if result.get("code") == 0:
        return result
    else:
        raise Exception(f"添加权限成员失败: {result}")


def transfer_owner(document_id, user_id):
    """转移文档所有权 - 必须使用 user_access_token 和 SDK"""
    try:
        import lark_oapi as lark
        from lark_oapi.api.drive.v1 import TransferOwnerPermissionMemberRequest, Owner
    except ImportError:
        raise Exception("lark-oapi SDK 未安装，请运行: pip install lark-oapi")

    config = load_config()
    if not config:
        raise Exception("无法加载配置文件")

    # 获取 user_access_token
    token_path = Path(__file__).parent.parent.parent.parent / "feishu-token.json"
    if not token_path.exists():
        raise Exception("user_access_token 文件不存在，请先运行授权: python feishu_auth.py")

    try:
        with open(token_path, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        # 支持 access_token 和 user_access_token 两种格式
        user_token = token_data.get("user_access_token") or token_data.get("access_token")
    except Exception as e:
        raise Exception(f"读取 user_access_token 失败: {e}")

    if not user_token:
        raise Exception("user_access_token 不存在")

    # 创建使用 user_access_token 的客户端
    client = lark.Client.builder() \
        .app_id(config.get('FEISHU_APP_ID', '')) \
        .app_secret(config.get('FEISHU_APP_SECRET', '')) \
        .build()

    # 创建请求选项，设置 user_access_token
    request_option = lark.RequestOption.builder() \
        .user_access_token(user_token) \
        .build()

    # 构建转移所有权请求
    request = TransferOwnerPermissionMemberRequest.builder() \
        .token(document_id) \
        .type("docx") \
        .need_notification(True) \
        .remove_old_owner(False) \
        .stay_put(False) \
        .old_owner_perm("view") \
        .request_body(Owner.builder()
            .member_type("openid")
            .member_id(user_id)
            .build()) \
        .build()

    # 执行转移
    response = client.drive.v1.permission_member.transfer_owner(request, request_option)

    if not response.success():
        raise Exception(f"转移所有权失败: code={response.code}, msg={response.msg}")

    return response


def main():
    """主函数 - 命令行入口"""
    # 解析参数
    title = "未命名文档"
    output_dir = Path("output")

    if len(sys.argv) >= 2:
        title = sys.argv[1]

    if len(sys.argv) >= 3:
        output_dir = Path(sys.argv[2])

    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载配置
    config = load_config()
    if not config:
        print("[feishu-doc-creator-with-permission] Error: Unable to load config")
        sys.exit(1)

    print("=" * 70)
    print("文档创建 + 权限管理（原子操作）")
    print("=" * 70)
    print(f"文档标题: {title}")
    print()

    # 权限配置
    collaborator_id = config.get('FEISHU_AUTO_COLLABORATOR_ID')
    collaborator_type = config.get('FEISHU_AUTO_COLLABORATOR_TYPE', 'openid')
    collaborator_perm = config.get('FEISHU_AUTO_COLLABORATOR_PERM', 'full_access')

    # 结果数据
    result = {
        "title": title,
        "created_at": datetime.now().isoformat(),
        "permission": {
            "collaborator_added": False,
            "owner_transferred": False,
            "user_has_full_control": False,
            "collaborator_id": collaborator_id
        },
        "errors": []
    }

    # ========== 第一步：创建文档 ==========
    print("[步骤 1/3] 创建文档 (tenant_access_token)...")
    try:
        token = get_access_token(config, use_user_token=False)
        doc_id = create_document(token, config, title)
        result["document_id"] = doc_id
        result["document_url"] = f"{config.get('FEISHU_WEB_DOMAIN', 'https://feishu.cn')}/docx/{doc_id}"
        print(f"[OK] 文档创建成功")
        print(f"     文档ID: {doc_id}")
    except Exception as e:
        error_msg = str(e)
        result["errors"].append(f"创建文档失败: {error_msg}")
        print(f"[FAIL] 创建文档失败: {error_msg}")
        # 保存失败结果并退出
        result_file = output_dir / "doc_with_permission.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        sys.exit(1)

    # ========== 第二步：添加协作者权限 ==========
    print("\n[步骤 2/3] 添加协作者权限 (tenant_access_token)...")
    if collaborator_id:
        try:
            add_permission_member(token, config, doc_id, collaborator_id, collaborator_type, collaborator_perm)
            result["permission"]["collaborator_added"] = True
            print(f"[OK] 协作者权限添加成功")
            print(f"     协作者ID: {collaborator_id}")
        except Exception as e:
            error_msg = str(e)
            result["errors"].append(f"添加协作者失败: {error_msg}")
            print(f"[FAIL] 添加协作者失败: {error_msg}")
            print("[WARN] 用户可能无法编辑文档")
    else:
        print("[SKIP] 未配置协作者 ID，跳过")
        result["errors"].append("未配置协作者 ID，跳过权限添加")

    # ========== 第三步：转移所有权 ==========
    print("\n[步骤 3/3] 转移所有权 (user_access_token)...")
    if result["permission"]["collaborator_added"]:
        try:
            transfer_owner(doc_id, collaborator_id)
            result["permission"]["owner_transferred"] = True
            result["permission"]["user_has_full_control"] = True
            print(f"[OK] 所有权转移成功")
            print(f"     用户现在拥有完全控制权（可编辑+可删除）")
        except Exception as e:
            error_msg = str(e)
            result["errors"].append(f"转移所有权失败: {error_msg}")
            print(f"[WARN] 转移所有权失败: {error_msg}")
            print("[INFO] 用户可以编辑文档，但无法删除文档")
    else:
        print("[SKIP] 跳过所有权转移（因为添加协作者失败）")

    # 保存结果
    result_file = output_dir / "doc_with_permission.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print()
    print("=" * 70)
    print("操作完成")
    print("=" * 70)
    print(f"文档URL: {result['document_url']}")
    print(f"协作者添加: {result['permission']['collaborator_added']}")
    print(f"所有权转移: {result['permission']['owner_transferred']}")
    print(f"用户完全控制: {result['permission']['user_has_full_control']}")
    print(f"\n输出文件: {result_file}")
    print(f"\n[OUTPUT] {result_file}")


if __name__ == "__main__":
    main()
