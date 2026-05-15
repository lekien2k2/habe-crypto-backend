# Tài liệu Yêu cầu

## Giới thiệu

Tài liệu này mô tả các yêu cầu cho việc triển khai hạ tầng lưu trữ Amazon S3 phân tầng (tiered storage) bằng Terraform. Hệ thống bao gồm các bucket S3 với nhiều tầng lưu trữ (Standard và Glacier), lifecycle rules để tự động chuyển đổi dữ liệu giữa các tầng nhằm tối ưu chi phí, mã hóa dữ liệu, và cấu hình IAM theo nguyên tắc least privilege.

## Thuật ngữ

- **Terraform_Module**: Module Terraform chịu trách nhiệm khởi tạo và quản lý toàn bộ hạ tầng S3 tiered storage
- **Standard_Bucket**: Bucket S3 sử dụng storage class STANDARD, chứa dữ liệu được truy cập thường xuyên
- **Archive_Bucket**: Bucket S3 sử dụng storage class GLACIER hoặc STANDARD_IA, chứa dữ liệu ít được truy cập
- **Lifecycle_Rule**: Quy tắc vòng đời được cấu hình trên S3 bucket để tự động chuyển đổi storage class của object sau một khoảng thời gian xác định
- **IAM_Policy**: Chính sách IAM định nghĩa quyền truy cập vào tài nguyên AWS
- **IAM_Role**: Vai trò IAM được gán cho Backend service để truy cập S3
- **Backend_Service**: Dịch vụ backend được phép truy cập các bucket S3
- **Encryption_Configuration**: Cấu hình mã hóa server-side trên bucket S3

## Yêu cầu

### Yêu cầu 1: Khởi tạo Standard Bucket

**User Story:** Là một DevOps engineer, tôi muốn có một bucket S3 Standard để lưu trữ dữ liệu được truy cập thường xuyên với mã hóa được bật mặc định.

#### Tiêu chí chấp nhận

1. THE Terraform_Module SHALL tạo một Standard_Bucket với storage class mặc định là STANDARD
2. THE Terraform_Module SHALL cấu hình Encryption_Configuration trên Standard_Bucket sử dụng server-side encryption với AES-256 (SSE-S3) hoặc AWS KMS (SSE-KMS)
3. THE Terraform_Module SHALL bật versioning trên Standard_Bucket
4. THE Terraform_Module SHALL chặn public access trên Standard_Bucket bằng cách bật tất cả các tùy chọn Block Public Access

### Yêu cầu 2: Khởi tạo Archive Bucket

**User Story:** Là một DevOps engineer, tôi muốn có một bucket S3 với storage class Glacier hoặc Standard-IA để lưu trữ dữ liệu ít được truy cập với chi phí thấp hơn.

#### Tiêu chí chấp nhận

1. THE Terraform_Module SHALL tạo một Archive_Bucket riêng biệt với Standard_Bucket
2. THE Terraform_Module SHALL cấu hình Encryption_Configuration trên Archive_Bucket sử dụng server-side encryption với AES-256 (SSE-S3) hoặc AWS KMS (SSE-KMS)
3. THE Terraform_Module SHALL bật versioning trên Archive_Bucket
4. THE Terraform_Module SHALL chặn public access trên Archive_Bucket bằng cách bật tất cả các tùy chọn Block Public Access

### Yêu cầu 3: Lifecycle Rule cho việc chuyển đổi tầng lưu trữ

**User Story:** Là một DevOps engineer, tôi muốn cấu hình lifecycle rule để tự động chuyển dữ liệu từ Standard sang Glacier sau một khoảng thời gian, nhằm tối ưu chi phí lưu trữ.

#### Tiêu chí chấp nhận

1. THE Terraform_Module SHALL cấu hình một Lifecycle_Rule trên Standard_Bucket để chuyển object sang storage class GLACIER
2. THE Terraform_Module SHALL đặt thời gian chuyển đổi mặc định của Lifecycle_Rule là 30 ngày kể từ ngày tạo object
3. THE Terraform_Module SHALL cho phép cấu hình thời gian chuyển đổi thông qua biến Terraform (variable) để người dùng có thể tùy chỉnh
4. THE Terraform_Module SHALL đặt trạng thái của Lifecycle_Rule là "Enabled"
5. WHEN một object trong Standard_Bucket đạt đến thời gian chuyển đổi đã cấu hình, THE Lifecycle_Rule SHALL tự động chuyển object đó sang storage class GLACIER

### Yêu cầu 4: IAM Role cho Backend Service

**User Story:** Là một DevOps engineer, tôi muốn tạo IAM Role cho Backend service với quyền tối thiểu (least privilege) để đảm bảo an toàn bảo mật.

#### Tiêu chí chấp nhận

1. THE Terraform_Module SHALL tạo một IAM_Role dành riêng cho Backend_Service
2. THE Terraform_Module SHALL cấu hình trust policy trên IAM_Role cho phép Backend_Service assume role
3. THE Terraform_Module SHALL tạo một IAM_Policy chỉ cấp quyền s3:PutObject và s3:GetObject
4. THE Terraform_Module SHALL giới hạn IAM_Policy chỉ áp dụng trên resource ARN của Standard_Bucket và Archive_Bucket
5. THE Terraform_Module SHALL gắn IAM_Policy vào IAM_Role
6. THE Terraform_Module SHALL không cấp bất kỳ quyền S3 nào khác ngoài s3:PutObject và s3:GetObject cho IAM_Role

### Yêu cầu 5: Cấu hình Terraform Module

**User Story:** Là một DevOps engineer, tôi muốn module Terraform được cấu hình linh hoạt với các biến đầu vào và đầu ra rõ ràng để dễ dàng tái sử dụng.

#### Tiêu chí chấp nhận

1. THE Terraform_Module SHALL khai báo biến cho tên bucket (bucket name prefix)
2. THE Terraform_Module SHALL khai báo biến cho thời gian chuyển đổi lifecycle (tính bằng ngày)
3. THE Terraform_Module SHALL khai báo biến cho AWS region
4. THE Terraform_Module SHALL xuất (output) ARN của Standard_Bucket
5. THE Terraform_Module SHALL xuất (output) ARN của Archive_Bucket
6. THE Terraform_Module SHALL xuất (output) ARN của IAM_Role
7. THE Terraform_Module SHALL khai báo required provider là hashicorp/aws với version constraint cụ thể

### Yêu cầu 6: Xử lý lỗi và validation

**User Story:** Là một DevOps engineer, tôi muốn module Terraform có validation cho các biến đầu vào để tránh cấu hình sai.

#### Tiêu chí chấp nhận

1. IF giá trị biến thời gian chuyển đổi lifecycle nhỏ hơn 1 ngày, THEN THE Terraform_Module SHALL báo lỗi validation
2. IF giá trị biến tên bucket prefix chứa ký tự không hợp lệ (không phải chữ thường, số, hoặc dấu gạch ngang), THEN THE Terraform_Module SHALL báo lỗi validation
3. THE Terraform_Module SHALL sử dụng tags mặc định bao gồm Environment và ManagedBy trên tất cả tài nguyên
