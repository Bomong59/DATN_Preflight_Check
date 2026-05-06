import streamlit as st
import cv2
import wave
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import socket
import time

# --- 1. CÀI ĐẶT GIAO DIỆN CHUNG ---
st.set_page_config(page_title="Pre-flight Check", page_icon="🚀", layout="centered")
st.title("🚀 Hệ thống Kiểm tra Sẵn sàng Giảng dạy")
st.markdown("Vui lòng hoàn thành kiểm tra thiết bị và đường truyền trước khi vào lớp.")

# --- 2. BỘ NHỚ TẠM (Giữ nguyên trạng thái khi thao tác) ---
if 'cam_status' not in st.session_state: st.session_state.cam_status = "Chưa test"
if 'mic_status' not in st.session_state: st.session_state.mic_status = "Chưa test"
if 'net_status' not in st.session_state: st.session_state.net_status = "Chưa test" # Biến mới cho Mạng

if 'cam_image' not in st.session_state: st.session_state.cam_image = None
if 'cam_caption' not in st.session_state: st.session_state.cam_caption = ""
if 'mic_message' not in st.session_state: st.session_state.mic_message = ""
if 'net_message' not in st.session_state: st.session_state.net_message = "" # Biến mới cho Mạng

# --- 3. KHU VỰC NHẬP THÔNG TIN ---
ten_gv = st.text_input("👤 Nhập tên Giảng viên:", placeholder="VD: Nguyễn Văn A")
st.divider()

# --- 4. BƯỚC 1: KIỂM TRA CAMERA (TÍCH HỢP AI NHẬN DIỆN KHUÔN MẶT) ---
st.subheader("📷 Bước 1: Kiểm tra Camera (AI Face Detection)")
st.markdown("💡 *Hệ thống sử dụng AI (Computer Vision) để chống gian lận. Vui lòng nhìn thẳng vào Camera và bấm **Take Photo**.*")

cam_buffer = st.camera_input("Luồng Video Trực Tiếp")

if cam_buffer is not None:
    # 1. Đọc dữ liệu ảnh từ lúc bấm chụp
    bytes_data = cam_buffer.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    gray_frame = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
    
    # 2. Gọi "Bộ não" AI nhận diện khuôn mặt (đã có sẵn trong OpenCV)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # 3. AI bắt đầu quét tìm khuôn mặt trong ảnh
    faces = face_cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    
    # 4. Vẽ ô vuông xanh lá cây quanh các khuôn mặt tìm được
    for (x, y, w, h) in faces:
        cv2.rectangle(cv2_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
    # Hiển thị bức ảnh AI phân tích xong lên cho người dùng xem
    st.image(cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB), caption=f"Phân tích AI: Nhận diện được {len(faces)} khuôn mặt")
    
    # 5. Logic chống gian lận tuyệt đối
    if len(faces) == 0:
        st.session_state.cam_status = "Lỗi (Không thấy người)"
        st.error("❌ CẢNH BÁO: Không tìm thấy khuôn mặt! Vui lòng không dùng ảnh giả, vật thể lạ hoặc lấy tay che Camera.")
    else:
        st.session_state.cam_status = "Tốt"
        st.success("✅ AI xác thực thành công! Đã phát hiện khuôn mặt Giảng viên hợp lệ.")
else:
    st.session_state.cam_status = "Chưa test"

# --- 5. BƯỚC 2: KIỂM TRA MICRO (CLOUD-READY) ---
st.subheader("🎙️ Bước 2: Kiểm tra Micro (Web Audio)")
st.markdown("💡 *Bấm vào biểu tượng Micro, nói 'Alo Alo' để thu âm thử nhé.*")

audio_buffer = st.audio_input("Thu âm giọng nói của bạn")

if audio_buffer is not None:
    import wave
    # Đọc file âm thanh trực tiếp từ bộ nhớ đệm của trình duyệt
    with wave.open(audio_buffer, 'rb') as w:
        frames = w.readframes(w.getnframes())
        audio_data = np.frombuffer(frames, dtype=np.int16)
        
        # Tính toán biên độ âm thanh (Int16 có dải từ -32768 đến 32767)
        if len(audio_data) > 0:
            volume = np.max(np.abs(audio_data))
        else:
            volume = 0
            
    st.write(f"**Thông số quét:** Biên độ âm thanh: {volume}/32768")
    
    # Ngưỡng 500 là đủ để lọc tiếng ồn môi trường
    if volume > 500:
        st.session_state.mic_status = "Tốt"
        st.success("✅ Micro thu âm cực kỳ rõ ràng!")
    else:
        st.session_state.mic_status = "Lỗi (Không có tiếng)"
        st.error("❌ Không nghe thấy tiếng! Vui lòng nói to hơn hoặc kiểm tra lại Micro.")
else:
    st.session_state.mic_status = "Chưa test"

# --- 6. BƯỚC 3: KIỂM TRA MẠNG (TÍNH NĂNG MỚI) ---
st.subheader("🌐 Bước 3: Kiểm tra Băng thông & Độ trễ (Ping)")
if st.button("Đo kiểm mạng (Ping Test)"):
    with st.spinner("Đang gửi gói tin đến máy chủ Google (8.8.8.8)..."):
        try:
            # Gửi 3 gói tin và lấy thời gian trung bình
            tong_thoi_gian = 0
            for i in range(3):
                start = time.time()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0) # Quá 2 giây không phản hồi là đứt mạng
                s.connect(("8.8.8.8", 53))
                s.close()
                tong_thoi_gian += (time.time() - start) * 1000 # Đổi ra ms
                time.sleep(0.1)
                
            ping_trung_binh = tong_thoi_gian / 3
            
            # Đánh giá chất lượng mạng (QoS)
            if ping_trung_binh < 80:
                st.session_state.net_status = "Tốt"
                st.session_state.net_message = f"✅ Mạng rất mượt! Độ trễ: {ping_trung_binh:.0f} ms (Thích hợp dạy Livestream 1080p)"
            elif ping_trung_binh < 200:
                st.session_state.net_status = "Kém"
                st.session_state.net_message = f"⚠️ Mạng hơi chậm! Độ trễ: {ping_trung_binh:.0f} ms (Có thể bị giật hình đôi chút)"
            else:
                st.session_state.net_status = "Lỗi (Lag)"
                st.session_state.net_message = f"❌ Mạng quá lag! Độ trễ: {ping_trung_binh:.0f} ms. Học sinh sẽ không thể nghe bạn nói!"
                
        except Exception:
            st.session_state.net_status = "Lỗi (Mất mạng)"
            st.session_state.net_message = "❌ Không có kết nối Internet! Vui lòng cắm lại cáp mạng hoặc kiểm tra Wifi."

if st.session_state.net_message != "":
    if st.session_state.net_status == "Tốt":
        st.success(st.session_state.net_message)
    elif st.session_state.net_status == "Kém":
        st.warning(st.session_state.net_message)
    else:
        st.error(st.session_state.net_message)

st.divider()

# --- 7. BƯỚC 4: GỬI BÁO CÁO (KHÓA CHẶT 3 ĐIỀU KIỆN) ---
sheader("📤 Bước 4: Chốt Ca Dạy")
st.write(f"**Camera:** {st.session_state.cam_status} | **Micro:** {st.session_state.mic_status} | **Mạng:** {st.session_state.net_status}")

if st.button("Gửi Báo Cáo Lên Hệ Thống", type="primary"):
    if not ten_gv:
        st.warning("⚠️ Bạn chưa nhập tên Giảng viên!")
    elif st.session_state.cam_status != "Tốt":
        st.error("🛑 Không thể gửi! Vui lòng hoàn thành test Camera.")
    elif st.session_state.mic_status != "Tốt":
        st.error("🛑 Không t.subthể gửi! Vui lòng hoàn thành test Micro.")
    elif "Lỗi" in st.session_state.net_status or st.session_state.net_status == "Chưa test":
        st.error("🛑 Không thể gửi! Mạng của bạn chưa test hoặc đang bị rớt mạng.")
    else:
        with st.spinner("Đang đẩy dữ liệu lên máy chủ đám mây..."):
            try:
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                import json
                # Lấy nội dung chìa khóa từ két sắt Streamlit
                creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
                # Đăng nhập bằng dữ liệu vừa lấy
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                client = gspread.authorize(creds)
                sheet = client.open("DuLieu_Preflight").sheet1

                thoi_gian = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Nếu Mạng là "Kém" (Vàng) thì vẫn cho gửi nhưng đánh dấu cảnh báo
                trang_thai_chung = "PASS" if st.session_state.net_status == "Tốt" else "PASS (Cảnh báo mạng)"
                
                # Sửa mảng dữ liệu để khớp với 6 cột trên Google Sheets
                du_lieu = [
                    thoi_gian, 
                    ten_gv, 
                    st.session_state.mic_status, 
                    st.session_state.cam_status, 
                    st.session_state.net_status, # Cột mới thêm
                    trang_thai_chung
                ]
                sheet.append_row(du_lieu)
                
                st.success("🎉 Đã chứng thực thành công! Dữ liệu đã được lưu trên máy chủ quản lý.")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Lỗi kết nối Google Sheets: {e}")