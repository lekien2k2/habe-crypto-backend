# Tài liệu Yêu cầu

## Giới thiệu

Tài liệu này mô tả các yêu cầu cho việc xây dựng hệ thống mã hóa dựa trên thuộc tính phân cấp (Hierarchical Attribute-Based Encryption - HABE) kết hợp với CP-ABE (Ciphertext-Policy Attribute-Based Encryption). Hệ thống bao gồm hai phần chính: (1) Core Crypto Module thực hiện các phép toán mã hóa/giải mã dựa trên chính sách truy cập và thuộc tính người dùng, và (2) Backend API Server đóng vai trò proxy giữa người dùng và AWS S3, tích hợp module mã hóa để bảo vệ dữ liệu trước khi lưu trữ.

Hệ thống sử dụng hạ tầng S3 tiered storage đã được triển khai sẵn (module `s3-tiered-storage`) làm tầng lưu trữ.

## Thuật ngữ

- **Crypto_Module**: Module mã hóa cốt lõi thực hiện các phép toán HABE/CP-ABE (Setup, KeyGen, Encrypt, Decrypt)
- **Backend_API**: Server API (FastAPI + Uvicorn) đóng vai trò proxy giữa client và AWS S3, tích hợp Crypto_Module
- **Master_Public_Key (MPK)**: Khóa công khai chính được tạo bởi hàm Setup, dùng để mã hóa dữ liệu
- **Master_Secret_Key (MSK)**: Khóa bí mật chính được tạo bởi hàm Setup, dùng để phát hành khóa người dùng
- **User_Secret_Key (USK)**: Khóa bí mật của người dùng được phát hành bởi hàm KeyGen dựa trên tập thuộc tính
- **Access_Policy**: Chính sách truy cập dạng cây logic (ví dụ: "Manager AND Department_A") xác định ai được phép giải mã
- **Attribute_Set**: Tập hợp các thuộc tính gán cho người dùng trong hệ thống phân cấp (ví dụ: ["Manager", "Department_A"])
- **Ciphertext**: Dữ liệu đã được mã hóa bằng Crypto_Module kèm theo Access_Policy
- **Plaintext**: Dữ liệu gốc trước khi mã hóa hoặc sau khi giải mã thành công
- **S3_Storage**: Hạ tầng lưu trữ AWS S3 tiered storage đã được triển khai sẵn (Standard và Archive bucket)
- **Charm_Crypto**: Thư viện mã hóa Python (Charm-crypto) hỗ trợ các scheme ABE
- **Client**: Ứng dụng phía người dùng gửi yêu cầu upload/download file qua Backend_API

## Yêu cầu

### Yêu cầu 1: Khởi tạo hệ thống mã hóa (Setup)

**User Story:** Là một quản trị viên hệ thống, tôi muốn khởi tạo các tham số mã hóa toàn cục để hệ thống HABE có thể hoạt động.

#### Tiêu chí chấp nhận

1. THE Crypto_Module SHALL cung cấp hàm Setup() trả về một cặp Master_Public_Key và Master_Secret_Key
2. WHEN hàm Setup() được gọi, THE Crypto_Module SHALL tạo Master_Public_Key và Master_Secret_Key dựa trên scheme CP-ABE
3. THE Crypto_Module SHALL đảm bảo Master_Public_Key có thể được phân phối công khai mà không ảnh hưởng đến bảo mật hệ thống
4. THE Crypto_Module SHALL đảm bảo Master_Secret_Key được giữ bí mật và chỉ được sử dụng bởi quản trị viên để phát hành khóa người dùng
5. WHEN hàm Setup() được gọi nhiều lần, THE Crypto_Module SHALL tạo ra các cặp khóa khác nhau mỗi lần

### Yêu cầu 2: Phát hành khóa người dùng (KeyGen)

**User Story:** Là một quản trị viên hệ thống, tôi muốn phát hành khóa cho người dùng dựa trên thuộc tính và vị trí trong hệ thống phân cấp, để kiểm soát quyền truy cập dữ liệu.

#### Tiêu chí chấp nhận

1. THE Crypto_Module SHALL cung cấp hàm KeyGen() nhận đầu vào là Master_Public_Key, Master_Secret_Key, và Attribute_Set của người dùng
2. WHEN hàm KeyGen() được gọi với một Attribute_Set hợp lệ, THE Crypto_Module SHALL trả về một User_Secret_Key tương ứng với tập thuộc tính đó
3. THE Crypto_Module SHALL hỗ trợ Attribute_Set chứa nhiều thuộc tính phân cấp (ví dụ: ["Company", "Department_A", "Manager"])
4. IF Attribute_Set rỗng hoặc không hợp lệ, THEN THE Crypto_Module SHALL trả về lỗi mô tả rõ nguyên nhân
5. THE Crypto_Module SHALL đảm bảo User_Secret_Key chỉ có thể giải mã dữ liệu mà Access_Policy được thỏa mãn bởi Attribute_Set tương ứng

### Yêu cầu 3: Mã hóa dữ liệu (Encrypt)

**User Story:** Là một người dùng, tôi muốn mã hóa file với một chính sách truy cập cụ thể, để chỉ những người có đủ thuộc tính mới có thể xem nội dung.

#### Tiêu chí chấp nhận

1. THE Crypto_Module SHALL cung cấp hàm Encrypt() nhận đầu vào là Master_Public_Key, Plaintext (dữ liệu file), và Access_Policy
2. WHEN hàm Encrypt() được gọi với Access_Policy hợp lệ, THE Crypto_Module SHALL trả về Ciphertext được mã hóa theo chính sách đó
3. THE Crypto_Module SHALL hỗ trợ Access_Policy dạng biểu thức logic với các toán tử AND và OR (ví dụ: "Manager AND Department_A")
4. IF Access_Policy có cú pháp không hợp lệ, THEN THE Crypto_Module SHALL trả về lỗi mô tả rõ nguyên nhân
5. THE Crypto_Module SHALL đảm bảo Ciphertext không thể giải mã nếu không có User_Secret_Key thỏa mãn Access_Policy
6. THE Crypto_Module SHALL xử lý được file có kích thước tùy ý mà không gây lỗi byte-level trong quá trình mã hóa

### Yêu cầu 4: Giải mã dữ liệu (Decrypt)

**User Story:** Là một người dùng có đủ quyền, tôi muốn giải mã file đã được mã hóa để xem nội dung gốc.

#### Tiêu chí chấp nhận

1. THE Crypto_Module SHALL cung cấp hàm Decrypt() nhận đầu vào là Master_Public_Key, User_Secret_Key, và Ciphertext
2. WHEN User_Secret_Key có Attribute_Set thỏa mãn Access_Policy của Ciphertext, THE Crypto_Module SHALL trả về Plaintext gốc
3. IF User_Secret_Key có Attribute_Set không thỏa mãn Access_Policy của Ciphertext, THEN THE Crypto_Module SHALL trả về lỗi từ chối truy cập
4. THE Crypto_Module SHALL đảm bảo Plaintext sau giải mã giống hệt byte-by-byte với Plaintext trước khi mã hóa (round-trip property)
5. IF Ciphertext bị hỏng hoặc không hợp lệ, THEN THE Crypto_Module SHALL trả về lỗi mô tả rõ nguyên nhân

### Yêu cầu 5: Tính đúng đắn của chu trình mã hóa/giải mã (Round-Trip)

**User Story:** Là một kỹ sư phần mềm, tôi muốn đảm bảo rằng quá trình mã hóa rồi giải mã luôn trả về dữ liệu gốc chính xác, để hệ thống đáng tin cậy.

#### Tiêu chí chấp nhận

1. FOR ALL Plaintext hợp lệ, WHEN Encrypt() rồi Decrypt() được thực hiện với khóa thỏa mãn Access_Policy, THE Crypto_Module SHALL trả về Plaintext giống hệt dữ liệu ban đầu
2. FOR ALL Attribute_Set thỏa mãn Access_Policy, THE Crypto_Module SHALL giải mã thành công Ciphertext được mã hóa với Access_Policy đó
3. FOR ALL Attribute_Set không thỏa mãn Access_Policy, THE Crypto_Module SHALL từ chối giải mã Ciphertext được mã hóa với Access_Policy đó
4. THE Crypto_Module SHALL duy trì tính đúng đắn round-trip cho file nhị phân (binary), văn bản (text), và file rỗng (empty)

### Yêu cầu 6: Backend API - Upload Flow

**User Story:** Là một người dùng, tôi muốn upload file lên hệ thống thông qua API, để file được mã hóa tự động theo chính sách truy cập trước khi lưu trữ trên S3.

#### Tiêu chí chấp nhận

1. THE Backend_API SHALL cung cấp endpoint POST để nhận file upload kèm thông tin Access_Policy từ Client
2. WHEN Client gửi file và Access_Policy hợp lệ, THE Backend_API SHALL gọi hàm Encrypt() của Crypto_Module để mã hóa file
3. WHEN mã hóa thành công, THE Backend_API SHALL sử dụng AWS SDK (Boto3) để upload Ciphertext lên S3_Storage
4. THE Backend_API SHALL lưu trữ Ciphertext vào bucket phù hợp trong S3_Storage (Standard hoặc Archive tùy theo cấu hình)
5. WHEN upload lên S3 thành công, THE Backend_API SHALL trả về response thành công cho Client kèm metadata của file (ID, tên, kích thước)
6. IF quá trình mã hóa thất bại, THEN THE Backend_API SHALL trả về HTTP error response với mã lỗi và mô tả nguyên nhân
7. IF quá trình upload lên S3 thất bại, THEN THE Backend_API SHALL trả về HTTP error response với mã lỗi và mô tả nguyên nhân
8. THE Backend_API SHALL thực hiện mã hóa trong RAM hoặc temporary storage, không lưu Plaintext ra đĩa vĩnh viễn

### Yêu cầu 7: Backend API - Download Flow

**User Story:** Là một người dùng có đủ quyền, tôi muốn download file từ hệ thống thông qua API, để file được giải mã tự động nếu tôi có đủ thuộc tính.

#### Tiêu chí chấp nhận

1. THE Backend_API SHALL cung cấp endpoint GET để Client yêu cầu download file theo ID
2. WHEN Client gửi yêu cầu download, THE Backend_API SHALL tải Ciphertext từ S3_Storage về
3. WHEN tải Ciphertext thành công, THE Backend_API SHALL gọi hàm Decrypt() của Crypto_Module với User_Secret_Key của Client
4. WHEN giải mã thành công, THE Backend_API SHALL trả về Plaintext (file gốc) cho Client
5. IF User_Secret_Key của Client không thỏa mãn Access_Policy, THEN THE Backend_API SHALL trả về HTTP 403 Forbidden
6. IF file không tồn tại trên S3_Storage, THEN THE Backend_API SHALL trả về HTTP 404 Not Found
7. IF quá trình tải từ S3 thất bại, THEN THE Backend_API SHALL trả về HTTP error response với mã lỗi và mô tả nguyên nhân
8. THE Backend_API SHALL thực hiện giải mã trong RAM hoặc temporary storage, không lưu Plaintext ra đĩa vĩnh viễn

### Yêu cầu 8: Backend API Server Configuration

**User Story:** Là một kỹ sư DevOps, tôi muốn Backend API được xây dựng trên FastAPI với Uvicorn để dễ dàng tích hợp với Charm-crypto và triển khai.

#### Tiêu chí chấp nhận

1. THE Backend_API SHALL được xây dựng bằng framework FastAPI chạy trên Uvicorn
2. THE Backend_API SHALL sử dụng Python làm ngôn ngữ lập trình chính để tích hợp trực tiếp với Charm_Crypto
3. THE Backend_API SHALL sử dụng Boto3 (AWS SDK for Python) để tương tác với S3_Storage
4. THE Backend_API SHALL cấu hình CORS cho phép Client truy cập API
5. THE Backend_API SHALL có endpoint health check để kiểm tra trạng thái hoạt động
6. IF kết nối đến S3_Storage không khả dụng, THEN THE Backend_API SHALL trả về HTTP 503 Service Unavailable tại health check

### Yêu cầu 9: Bảo mật và quản lý khóa

**User Story:** Là một quản trị viên bảo mật, tôi muốn hệ thống quản lý khóa an toàn để đảm bảo tính bảo mật của dữ liệu mã hóa.

#### Tiêu chí chấp nhận

1. THE Backend_API SHALL không lưu Master_Secret_Key trong source code hoặc file cấu hình dạng plaintext
2. THE Backend_API SHALL không ghi log nội dung Plaintext hoặc User_Secret_Key
3. THE Backend_API SHALL xóa dữ liệu tạm (Plaintext, Ciphertext trong RAM) sau khi hoàn thành xử lý request
4. IF một request xử lý thất bại giữa chừng, THEN THE Backend_API SHALL đảm bảo không có dữ liệu nhạy cảm bị rò rỉ trong log hoặc temporary storage
5. THE Crypto_Module SHALL sử dụng thư viện Charm_Crypto đã được kiểm chứng cho các phép toán mã hóa ABE

### Yêu cầu 10: Xử lý lỗi và validation đầu vào

**User Story:** Là một kỹ sư phần mềm, tôi muốn hệ thống có validation đầu vào chặt chẽ và xử lý lỗi rõ ràng để dễ debug và đảm bảo ổn định.

#### Tiêu chí chấp nhận

1. IF Client gửi request upload thiếu file hoặc Access_Policy, THEN THE Backend_API SHALL trả về HTTP 400 Bad Request với mô tả lỗi
2. IF Client gửi Access_Policy có cú pháp không hợp lệ, THEN THE Backend_API SHALL trả về HTTP 400 Bad Request với mô tả lỗi cú pháp
3. IF Client gửi request download thiếu thông tin xác thực (User_Secret_Key), THEN THE Backend_API SHALL trả về HTTP 401 Unauthorized
4. THE Backend_API SHALL trả về response lỗi theo format JSON thống nhất bao gồm: mã lỗi, mô tả, và timestamp
5. IF file upload vượt quá kích thước tối đa cho phép, THEN THE Backend_API SHALL trả về HTTP 413 Payload Too Large
