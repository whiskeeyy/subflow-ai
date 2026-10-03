# SubFlow AI — Đặc Tả Giao Thức API & WebSocket (API Reference)

Tài liệu này cung cấp chi tiết về giao thức kết nối, các điểm cuối REST API và cấu trúc thông điệp WebSocket thời gian thực của hệ thống **SubFlow AI**.

---

## 1. REST Endpoints

### 1.1. Upload Video
Tiếp nhận tệp video từ máy tính của người dùng và lưu trữ vào thư mục tác vụ mới.

- **URL**: `/api/upload`
- **Phương thức**: `POST`
- **Content-Type**: `multipart/form-data`
- **Tham số Request**:
  - `file`: Tệp video (hỗ trợ `.mp4`, `.mov`, `.mkv`, kích thước tối đa tùy thuộc vào dung lượng ổ đĩa).

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "task_id": "task_a1b2c3d4",
    "video_path": "D:\\DVRT\\outputs\\task_a1b2c3d4\\video_goc.mp4",
    "filename": "video_sample.mp4"
  }
  ```

- **Mã lỗi**:
  - `400 Bad Request`: Không có tệp đính kèm hoặc tên tệp không hợp lệ.
  - `500 Internal Server Error`: Không thể ghi tệp vào đĩa cứng.

---

### 1.2. Mở Thư Mục Cục Bộ
Kích hoạt trình quản lý tệp gốc của hệ điều hành (Windows Explorer, macOS Finder, Linux xdg-open) để mở thư mục thành phẩm.

- **URL**: `/api/open-folder`
- **Phương thức**: `GET`
- **Query Parameters**:
  - `path`: Đường dẫn tuyệt đối đến thư mục cần mở (bắt buộc phải nằm trong thư mục `outputs/`).

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message": "Đã mở thư mục: D:\\DVRT\\outputs\\task_a1b2c3d4"
  }
  ```

- **Mã lỗi**:
  - `400 Bad Request`: Đường dẫn không hợp lệ hoặc cố tình truy cập ngoài phạm vi thư mục cho phép (Path Traversal Protection).
  - `500 Internal Server Error`: Lỗi khởi chạy ứng dụng thám hiểm tệp.

---

### 1.3. Phục Vụ Tệp Tĩnh (Static Files)
Hệ thống gắn kết trực tiếp thư mục `outputs/` để hỗ trợ trình duyệt phát video và tải file:

- **URL Pattern**: `/outputs/{task_id}/{file_name}`
- **Ví dụ**:
  - Video gốc: `/outputs/task_a1b2c3d4/video_goc.mp4`
  - Phụ đề SRT: `/outputs/task_a1b2c3d4/sub_viet.srt`
  - Video hoàn chỉnh: `/outputs/task_a1b2c3d4/final_video.mp4`

---

## 2. Giao Thức WebSocket (`/ws/process`)

Quy trình xử lý hai giai đoạn (Human-in-the-loop) giao tiếp thời gian thực qua giao thức WebSocket hai chiều.

- **URL**: `ws://<host>:<port>/ws/process` hoặc `wss://...`

```
Client                                      Server
  │                                           │
  ├─── 1. Kết nối & Gửi Init Payload ────────►│
  │    { "task_id": "task_..." }              │
  │                                           ├─── Phase 1: Bóc sub & dịch
  │◄── 2. Phát PROGRESS (20%, 50%, 75%) ──────┤
  │                                           │
  │◄── 3. Phát ACTION_REQUIRED ───────────────┤ (Tạm dừng)
  │    { srt_content, video_url }             │
  │                                           │
  │    (Người dùng xem preview & chỉnh sửa)   │
  │                                           │
  ├─── 4. Gửi RESUME_WITH_SCRIPT ────────────►│
  │    { edited_srt, sub_style }              │
  │                                           ├─── Phase 2: Burn phụ đề FFmpeg
  │◄── 5. Phát PROGRESS (90%) ────────────────┤
  │                                           │
  │◄── 6. Phát SUCCESS (final_video.mp4) ─────┤
  │                                           ▼
```

---

### 2.1. Thông Điệp từ Client gửi lên Server

#### A. Khởi tạo quy trình (Init)
Gửi ngay sau khi thiết lập kết nối WebSocket thành công:
```json
{
  "task_id": "task_a1b2c3d4"
}
```

#### B. Xác nhận & Tiếp tục Phase 2 (Resume With Script)
Gửi khi người dùng đã duyệt xong kịch bản phụ đề và tùy biến style:
```json
{
  "action": "RESUME_WITH_SCRIPT",
  "edited_srt": "1\n00:00:00,000 --> 00:00:01,280\nTên tôi là YT\n\n2\n00:00:03,320 --> 00:00:04,100\nỞ trên tòa nhà...",
  "sub_style": {
    "color_bgr": "&H0000FFFF&",
    "font_size": 20,
    "margin_v": 140
  }
}
```

#### C. Hủy tác vụ (Cancel)
```json
{
  "action": "CANCEL"
}
```

---

### 2.2. Thông Điệp từ Server phát xuống Client

#### A. Tiến độ xử lý (PROGRESS)
```json
{
  "status": "PROGRESS",
  "percent": 50,
  "step": "TRANSCRIBE",
  "message": "Đang gọi faster-whisper cục bộ để bóc tách lời thoại tiếng Trung và tạo mốc thời gian SRT..."
}
```

#### B. Yêu cầu người dùng can thiệp (ACTION_REQUIRED)
Kích hoạt giai đoạn Human Review và nạp video vào Live Preview Player:
```json
{
  "status": "ACTION_REQUIRED",
  "action": "EDIT_SCRIPT",
  "task_id": "task_a1b2c3d4",
  "srt_content": "1\n00:00:00,000 --> 00:00:01,280\nTên tôi là YT\n\n...",
  "video_url": "/outputs/task_a1b2c3d4/video_goc.mp4",
  "message": "Kịch bản phụ đề tiếng Việt đã sẵn sàng! Bạn có thể xem trước video và tùy chỉnh phụ đề trực tiếp."
}
```

#### C. Hoàn tất thành công (SUCCESS)
```json
{
  "status": "SUCCESS",
  "task_id": "task_a1b2c3d4",
  "output_dir": "D:\\DVRT\\outputs\\task_a1b2c3d4",
  "files": {
    "video_goc": "D:\\DVRT\\outputs\\task_a1b2c3d4\\video_goc.mp4",
    "sub_viet": "D:\\DVRT\\outputs\\task_a1b2c3d4\\sub_viet.srt",
    "final_video": "D:\\DVRT\\outputs\\task_a1b2c3d4\\final_video.mp4"
  },
  "relative_paths": {
    "final_video": "/outputs/task_a1b2c3d4/final_video.mp4",
    "video": "/outputs/task_a1b2c3d4/video_goc.mp4",
    "sub_viet": "/outputs/task_a1b2c3d4/sub_viet.srt"
  },
  "video_url": "/outputs/task_a1b2c3d4/final_video.mp4",
  "message": "Nhúng phụ đề vào video hoàn tất thành công! Đã giữ nguyên 100% âm thanh gốc."
}
```

#### D. Báo lỗi (ERROR)
```json
{
  "status": "ERROR",
  "message": "Lỗi ở Phase 2: FFmpeg render video thất bại: ..."
}
```
