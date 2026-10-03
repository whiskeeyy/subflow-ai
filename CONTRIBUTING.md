# Hướng Dẫn Đóng Góp (Contributing Guide)

Cảm ơn bạn đã quan tâm đến việc phát triển **SubFlow AI**! Chúng tôi hoan nghênh mọi đóng góp từ cộng đồng nhà phát triển và sáng tạo nội dung.

---

## 📌 Quy Trình Đóng Góp

1. **Fork** repository này về tài khoản GitHub của bạn.
2. Tạo nhánh mới (`git checkout -b feature/tinh-nang-moi` hoặc `fix/sua-loi`).
3. Thực hiện các chỉnh sửa, kiểm tra kỹ lưỡng các module:
   - Backend: FastAPI, WebSocket, FFmpeg sub filter
   - Frontend: ES Modules trong `frontend/js/`, giao diện Tailwind CSS
4. Viết commit message rõ ràng, dễ hiểu theo chuẩn [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: thêm tùy chọn căn lề phụ đề trái/phải`
   - `fix: xử lý lỗi đường dẫn file chứa ký tự đặc biệt`
   - `docs: cập nhật tài liệu API`
5. Push nhánh lên fork của bạn (`git push origin feature/tinh-nang-moi`).
6. Tạo một **Pull Request (PR)** mới với mô tả chi tiết về các thay đổi.

---

## 💻 Chuẩn Bị Môi Trường Phát Triển

1. **Clone repository**:
   ```bash
   git clone https://github.com/your-username/subflow-ai.git
   cd subflow-ai
   ```

2. **Cài đặt môi trường ảo**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Cài đặt FFmpeg**:
   - Cần đảm bảo FFmpeg đã có trong `PATH` hệ thống hoặc đặt trong thư mục `ffmpeg_bin/`.

4. **Khởi chạy máy chủ phát triển**:
   ```bash
   uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## 🛡️ Báo Cáo Sự Cố & Yêu Cầu Tính Năng

Nếu bạn phát hiện lỗi hoặc có đề xuất cải tiến:
- Mở một **Issue** trên GitHub với mô tả chi tiết các bước tái hiện lỗi.
- Đính kèm thông tin hệ điều hành, phiên bản Python và log hiển thị trong Console nếu có.
