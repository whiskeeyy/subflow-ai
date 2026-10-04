# SubFlow AI — Đặc Tả Giao Thức API & WebSocket (API Reference)

Tài liệu này cung cấp chi tiết về giao thức kết nối, các điểm cuối REST API và cấu trúc thông điệp WebSocket thời gian thực của hệ thống **SubFlow AI**.

---

## 1. REST Endpoints

### 1.1. Upload Video Đơn Lẻ
Tiếp nhận tệp video từ máy tính của người dùng và lưu trữ vào thư mục tác vụ mới.

- **URL**: `/api/upload`
- **Phương thức**: `POST`
- **Content-Type**: `multipart/form-data`
- **Tham số Request**:
  - `file`: Tệp video (hỗ trợ `.mp4`, `.mov`, `.mkv`).

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "task_id": "task_a1b2c3d4",
    "video_path": "D:\\DVRT\\outputs\\task_a1b2c3d4\\video_goc.mp4",
    "filename": "video_sample.mp4"
  }
  ```

---

### 1.2. Upload Video Hàng Loạt (Batch Upload)
Tiếp nhận nhiều tệp video cùng lúc và tự động đưa vào hàng đợi xử lý bóc tách & dịch thuật AI.

- **URL**: `/api/batch/upload`
- **Phương thức**: `POST`
- **Content-Type**: `multipart/form-data`
- **Tham số Request**:
  - `files`: Danh sách các tệp video.

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "enqueued_count": 5,
    "tasks": [
      {
        "task_id": "task_1a2b3c4d",
        "filename": "video_01.mp4",
        "status": "pending",
        "percent": 0,
        "message": "Đang xếp hàng chờ xử lý AI..."
      }
    ]
  }
  ```

---

### 1.3. Lấy Trạng Thái Hàng Đợi (Batch Status)
Truy vấn trạng thái và tiến độ xử lý của tất cả các video trong hàng đợi theo thời gian thực.

- **URL**: `/api/batch/status`
- **Phương thức**: `GET`

- **Phản hồi thành công (`200 OK`)**:
  ```json
  [
    {
      "task_id": "task_1a2b3c4d",
      "filename": "video_01.mp4",
      "status": "waiting_review",
      "percent": 75,
      "message": "Đã dịch xong. Chờ duyệt kịch bản!",
      "video_url": "/outputs/task_1a2b3c4d/video_goc.mp4",
      "srt_url": "/outputs/task_1a2b3c4d/sub_viet.srt",
      "final_video_url": "/outputs/task_1a2b3c4d/final_video.mp4"
    },
    {
      "task_id": "task_2e3f4g5h",
      "filename": "video_02.mp4",
      "status": "rendering",
      "percent": 85,
      "message": "Đang nhúng phụ đề bằng FFmpeg..."
    }
  ]
  ```

---

### 1.4. Lấy Chi Tiết Kịch Bản Tác Vụ
Nạp nội dung phụ đề SRT và video của một tác vụ cụ thể để hiển thị lên trình biên tập.

- **URL**: `/api/batch/task/{task_id}`
- **Phương thức**: `GET`

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "task": { "task_id": "task_1a2b3c4d", "filename": "video_01.mp4" },
    "srt_content": "1\n00:00:00,000 --> 00:00:01,280\nTên tôi là YT\n\n...",
    "video_url": "/outputs/task_1a2b3c4d/video_goc.mp4",
    "final_video_url": null
  }
  ```

---

### 1.5. Lưu Kịch Bản Đã Hiệu Đính
Ghi đè nội dung phụ đề sau khi người dùng chỉnh sửa trên bộ thẻ Cue Cards hoặc mã nguồn SRT.

- **URL**: `/api/batch/task/{task_id}/save-srt`
- **Phương thức**: `POST`
- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "srt_content": "1\n00:00:00,000 --> 00:00:01,280\nNội dung đã chỉnh sửa..."
  }
  ```

---

### 1.6. Kích Hoạt Nhúng Phụ Đề Đơn Lẻ (Non-blocking)
Khởi chạy tiến trình FFmpeg nhúng phụ đề cho một video cụ thể dưới dạng tác vụ chạy ngầm độc lập (không gây nghẽn trình duyệt hay khóa UI).

- **URL**: `/api/batch/render-task`
- **Phương thức**: `POST`
- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "task_id": "task_1a2b3c4d",
    "sub_style": {
      "color_bgr": "&H0000FFFF&",
      "font_size": 20,
      "margin_v": 140,
      "play_res_y": 1080
    }
  }
  ```

- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message": "Đã bắt đầu nhúng phụ đề vào video.",
    "task": {
      "task_id": "task_1a2b3c4d",
      "status": "rendering",
      "percent": 80,
      "message": "Đang chuẩn bị nhúng phụ đề..."
    }
  }
  ```

---

### 1.7. Kích Hoạt Nhúng Hàng Loạt (Batch Render All)
Nhúng phụ đề đồng thời cho toàn bộ các video đang ở trạng thái `waiting_review` (đã duyệt kịch bản).

- **URL**: `/api/batch/render-all`
- **Phương thức**: `POST`
- **Request Body**:
  ```json
  {
    "sub_style": {
      "color_bgr": "&H0000FFFF&",
      "font_size": 20,
      "margin_v": 140
    }
  }
  ```

---

### 1.8. Lịch Sử Dự Án (Project History)
Lấy danh sách các video đã thực hiện trong 30 ngày gần nhất để hiển thị trên History Drawer.

- **URL**: `/api/history`
- **Phương thức**: `GET`

- **Phản hồi thành công (`200 OK`)**:
  ```json
  [
    {
      "task_id": "task_1a2b3c4d",
      "filename": "video_sample.mp4",
      "status": "done",
      "date": "Hôm nay",
      "time": "14:32:05",
      "video_url": "/outputs/task_1a2b3c4d/video_goc.mp4",
      "srt_url": "/outputs/task_1a2b3c4d/sub_viet.srt",
      "final_video_url": "/outputs/task_1a2b3c4d/final_video.mp4"
    }
  ]
  ```

---

### 1.9. Mở Thư Mục Cục Bộ
Kích hoạt trình quản lý tệp gốc của hệ điều hành (Windows Explorer, macOS Finder, Linux xdg-open) để mở thư mục thành phẩm.

- **URL**: `/api/open-folder`
- **Phương thức**: `GET`
- **Query Parameters**:
  - `path`: Đường dẫn tuyệt đối đến thư mục cần mở (bắt buộc phải nằm trong thư mục lưu trữ đã cấu hình).

---

### 1.10. Lấy Cấu Hình & Chẩn Đoán Phần Cứng (Settings & Hardware Diagnostics)
Truy vấn toàn bộ thiết lập hiện tại kết hợp với thông tin tự động chẩn đoán phần cứng (GPU NVIDIA, VRAM, NVENC, mô hình AI khả dụng).

- **URL**: `/api/settings`
- **Phương thức**: `GET`
- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "settings": {
      "storage": {
        "output_dir": "D:\\DVRT\\outputs",
        "auto_cleanup_audio": true,
        "auto_cleanup_source_video": false
      },
      "ai": {
        "whisper_model": "base",
        "device": "auto",
        "language": "zh"
      },
      "hardware": {
        "encoder": "auto",
        "gpu_device_id": 0
      },
      "translation": {
        "engine": "google_gtx",
        "api_key": ""
      },
      "subtitle_preset": {
        "color_bgr": "&H0000FFFF&",
        "font_size": 20,
        "margin_v": 140,
        "font_name": "Arial Black"
      }
    },
    "diagnostics": {
      "has_nvidia_gpu": true,
      "gpu_name": "NVIDIA GeForce RTX 3050",
      "vram_gb": 6.0,
      "has_nvenc": true,
      "resolved_device": "cuda",
      "resolved_encoder": "h264_nvenc",
      "installed_models": ["base"]
    }
  }
  ```

---

### 1.11. Cập Nhật Cấu Hình Hệ Thống (Update Settings)
Lưu cấu hình người dùng vào `%APPDATA%\SubFlowAI\settings.json` (hoặc `settings.json` cục bộ) một cách nguyên tử (atomic), tự động kiểm tra quyền ghi thư mục xuất video.

- **URL**: `/api/settings`
- **Phương thức**: `POST`
- **Content-Type**: `application/json`
- **Body**: Đối tượng JSON chứa cấu hình từng phần hoặc toàn bộ.
- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message": "Đã lưu cài đặt thành công.",
    "settings": { ... }
  }
  ```

---

### 1.12. Mở Hộp Thoại Chọn Thư Mục Windows (Browse Folder)
Kích hoạt hộp thoại Windows Shell Folder Picker chuẩn để người dùng duyệt và chọn thư mục lưu trữ video mà không cần nhập đường dẫn thủ công.

- **URL**: `/api/settings/browse-folder`
- **Phương thức**: `POST`
- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "path": "D:\\MyVideos\\ExportSubFlow"
  }
  ```

---

### 1.13. Khôi Phục Cài Đặt Gốc (Reset Settings)
Đặt lại toàn bộ cấu hình về giá trị mặc định tối ưu nhất của nhà sản xuất.

- **URL**: `/api/settings/reset`
- **Phương thức**: `POST`
- **Phản hồi thành công (`200 OK`)**:
  ```json
  {
    "status": "success",
    "message": "Đã khôi phục cài đặt gốc.",
    "settings": { ... }
  }
  ```

---

## 2. Giao Thức WebSocket (`/ws/process`)

Quy trình xử lý tương tác thời gian thực (Human-in-the-loop) đối với chế độ upload video đơn lẻ.

- **URL**: `ws://<host>:<port>/ws/process` hoặc `wss://...`

```
Client                                      Server
  │                                           │
  ├─── 1. Kết nối & Gửi Init Payload ────────►│
  │    { "task_id": "task_..." }              │
  │                                           ├─── Bóc tách âm thanh & dịch thuật
  │◄── 2. Phát PROGRESS (20%, 50%, 75%) ──────┤
  │                                           │
  │◄── 3. Phát ACTION_REQUIRED ───────────────┤ (Tạm dừng chờ người dùng)
  │    { srt_content, video_url }             │
  │                                           │
  │    (Người dùng xem preview & chỉnh sửa)   │
  │                                           │
  ├─── 4. Gửi RESUME_WITH_SCRIPT ────────────►│
  │    { edited_srt, sub_style }              │
  │                                           ├─── Nhúng phụ đề bằng FFmpeg
  │◄── 5. Phát PROGRESS (90%) ────────────────┤
  │                                           │
  │◄── 6. Phát SUCCESS (final_video.mp4) ─────┤
  │                                           ▼
```

---

### 2.1. Thông Điệp từ Client gửi lên Server

#### A. Khởi tạo quy trình (Init)
```json
{
  "task_id": "task_a1b2c3d4"
}
```

#### B. Xác nhận & Nhúng Phụ Đề (Resume With Script)
```json
{
  "action": "RESUME_WITH_SCRIPT",
  "edited_srt": "1\n00:00:00,000 --> 00:00:01,280\nTên tôi là YT\n\n...",
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
  "message": "Đang gọi faster-whisper cục bộ để bóc tách lời thoại và tạo mốc thời gian SRT..."
}
```

#### B. Yêu cầu duyệt kịch bản (ACTION_REQUIRED)
```json
{
  "status": "ACTION_REQUIRED",
  "task_id": "task_a1b2c3d4",
  "srt_content": "1\n00:00:00,000 --> 00:00:01,280\nTên tôi là YT\n\n...",
  "video_url": "/outputs/task_a1b2c3d4/video_goc.mp4",
  "message": "Kịch bản phụ đề tiếng Việt đã sẵn sàng! Bạn có thể xem trước video và tùy chỉnh phụ đề trực tiếp."
}
```

#### C. Hoàn tất tác vụ (SUCCESS)
```json
{
  "status": "SUCCESS",
  "task_id": "task_a1b2c3d4",
  "video_url": "/outputs/task_a1b2c3d4/final_video.mp4",
  "output_dir": "D:\\DVRT\\outputs\\task_a1b2c3d4",
  "message": "Hoàn tất nhúng phụ đề vào video!"
}
```
