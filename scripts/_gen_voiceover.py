import asyncio
import os

import edge_tts

VOICE = "vi-VN-NamMinhNeural"
OUT_DIR = os.path.join("Deliverables", "evidence", "_voice")
os.makedirs(OUT_DIR, exist_ok=True)

BEATS = [
    ("b1", "Mỗi ngày, hàng trăm tin nhắn đổ về từ hàng chục nhóm chat. "
           "Một lời hẹn họp. Một deadline. Một lời hứa với đối tác. "
           "Tất cả bị chôn vùi — và bạn chỉ nhận ra khi đã quá muộn."),
    ("b2", "Đây là Orbit — trợ lý AI cá nhân, sống ngay bên trong app chat của bạn. "
           "Không cần chuyển app. Không cần nhớ. "
           "Orbit đọc hộ bạn — và luôn hỏi trước khi hành động."),
    ("b3", "Không cần ai mở app lên yêu cầu — Orbit tự phát hiện ngay lời hẹn trong tin nhắn, "
           "và chủ động gợi ý tạo nhắc việc. "
           "Nhưng Orbit không bao giờ tự ý hành động thay bạn. "
           "Mọi thao tác ghi lịch, gửi nhắc nhở — đều dừng lại, chờ đúng một cú xác nhận từ bạn. "
           "An toàn tuyệt đối, quyết định luôn ở trong tay người dùng."),
    ("b4", "Với một cuộc trò chuyện dài hàng trăm tin nhắn, chỉ một cú bấm — "
           "Orbit tóm tắt toàn bộ, và trích xuất chính xác từng việc cần làm vào Task Inbox — "
           "nơi ưu tiên đúng việc cần xử lý trước. "
           "Chấp nhận một gợi ý, Orbit tự đồng bộ thẳng lên Google Calendar thật — "
           "hai chiều, luôn khớp dữ liệu, không một thao tác thủ công nào."),
    ("b5", "Và Orbit chỉ đọc những gì bạn cho phép. "
           "Mỗi hội thoại, bạn tự cấp quyền — và có thể thu hồi bất cứ lúc nào. "
           "Mọi nội dung gửi đi đều minh bạch, không có gì diễn ra sau lưng bạn."),
    ("b6", "Ở quy mô đội nhóm, Orbit còn mở rộng thành các Agent theo từng phòng ban — "
           "tự tổng hợp báo cáo tình trạng công việc theo thời gian thực, "
           "để người quản lý không còn phải gom số liệu thủ công."),
    ("b7", "Orbit — không để bất kỳ việc gì trôi qua trong tin nhắn. "
           "Chủ động, an toàn, và luôn đồng hành cùng bạn."),
]


async def main():
    for name, text in BEATS:
        out = os.path.join(OUT_DIR, f"{name}.mp3")
        communicate = edge_tts.Communicate(text, VOICE, rate="+4%")
        await communicate.save(out)
        print("saved", out)


asyncio.run(main())
