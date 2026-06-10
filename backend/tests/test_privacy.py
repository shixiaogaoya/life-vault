from app.privacy.masking import (
    PrivacyMaskingOptions,
    mask_message_dict,
    mask_text,
    parse_custom_terms,
)


def test_mask_text_masks_common_sensitive_patterns():
    options = PrivacyMaskingOptions(enabled=True)
    text = (
        "电话 13812345678，身份证 11010119900101123X，"
        "邮箱 alice@example.com，路径 C:\\Users\\alice\\chat\\image.jpg"
    )

    masked = mask_text(text, options)

    assert "13812345678" not in masked
    assert "138****5678" in masked
    assert "11010119900101123X" not in masked
    assert "110101********123X" in masked
    assert "alice@example.com" not in masked
    assert "a***@example.com" in masked
    assert "C:\\Users\\alice" not in masked
    assert "[PATH]" in masked


def test_custom_terms_support_names_and_addresses():
    options = PrivacyMaskingOptions(
        enabled=True,
        custom_terms=("张三", "北京市海淀区"),
    )

    masked = mask_text("张三住在北京市海淀区，电话 13900001111", options)

    assert "张三" not in masked
    assert "北京市海淀区" not in masked
    assert masked.count("[MASKED]") == 2
    assert "139****1111" in masked


def test_mask_text_detects_common_chinese_addresses():
    options = PrivacyMaskingOptions(enabled=True)

    masked = mask_text("收货地址：北京市海淀区中关村大街27号", options)

    assert "北京市海淀区中关村大街27号" not in masked
    assert "[ADDRESS]" in masked


def test_mask_message_dict_masks_nested_raw_and_metadata():
    options = PrivacyMaskingOptions(enabled=True, custom_terms=("Alice",))
    message = {
        "content": "Alice 的手机号 13812345678",
        "sender_name": "Alice",
        "raw": {"path": "/Users/alice/WeChat/file.txt"},
        "metadata": {"email": "alice@example.com"},
    }

    masked = mask_message_dict(message, options)

    assert masked is not message
    assert "Alice" not in str(masked)
    assert "13812345678" not in str(masked)
    assert "alice@example.com" not in str(masked)
    assert "/Users/alice" not in str(masked)
    assert masked["metadata"]["privacy_masking"]["enabled"] is True


def test_mask_message_dict_detects_chinese_names_from_message_fields():
    options = PrivacyMaskingOptions(enabled=True)
    message = {
        "content": "张三说稍后到",
        "sender_name": "张三",
        "chat_name": "项目群",
        "metadata": {},
    }

    masked = mask_message_dict(message, options)

    assert "张三" not in str(masked)
    assert "项目群" in str(masked)
    assert masked["metadata"]["privacy_masking"]["custom_term_count"] == 1
    assert "name" in masked["metadata"]["privacy_masking"]["rules"]


def test_parse_custom_terms_accepts_commas_and_newlines():
    assert parse_custom_terms("张三, 李四\n王五，张三") == ("张三", "李四", "王五")
