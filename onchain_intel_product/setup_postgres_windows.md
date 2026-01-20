# Hướng dẫn cài đặt PostgreSQL trên Windows

## 1. Cài đặt PostgreSQL

### Tải và cài đặt:
1. Truy cập: https://www.postgresql.org/download/windows/
2. Tải PostgreSQL 14+ installer
3. Chạy installer và làm theo hướng dẫn
4. **Quan trọng**: Ghi nhớ password cho user `postgres`

### Kiểm tra cài đặt:
```cmd
# Mở Command Prompt và test
psql --version
```

## 2. Tạo Database và User

### Cách 1: Sử dụng pgAdmin (GUI)
1. Mở pgAdmin (đã cài cùng PostgreSQL)
2. Kết nối với server localhost
3. Tạo database mới: `bitcoin_onchain_signals`
4. Tạo user mới: `onchain_user` với password `Cuongnv123456`

### Cách 2: Command Line
```cmd
# Mở Command Prompt as Administrator
# Kết nối với PostgreSQL
psql -U postgres -h localhost

# Trong psql prompt, chạy:
CREATE DATABASE bitcoin_onchain_signals;
CREATE USER onchain_user WITH PASSWORD 'Cuongnv123456';
GRANT ALL PRIVILEGES ON DATABASE bitcoin_onchain_signals TO onchain_user;
\q
```

## 3. Kiểm tra kết nối

```cmd
# Test kết nối với user mới
psql -U onchain_user -d bitcoin_onchain_signals -h localhost
# Nhập password: Cuongnv123456
# Nếu thành công, sẽ thấy prompt: bitcoin_onchain_signals=>
\q
```

## 4. Cấu hình Windows Service

### Đảm bảo PostgreSQL service đang chạy:
```cmd
# Kiểm tra service
sc query postgresql-x64-14

# Start service nếu chưa chạy
net start postgresql-x64-14
```

## 5. Troubleshooting

### Lỗi "password authentication failed":
1. Kiểm tra file `pg_hba.conf`:
   - Location: `C:\Program Files\PostgreSQL\14\data\pg_hba.conf`
   - Đảm bảo có dòng: `host all all 127.0.0.1/32 md5`

2. Restart PostgreSQL service:
   ```cmd
   net stop postgresql-x64-14
   net start postgresql-x64-14
   ```

### Lỗi "connection refused":
1. Kiểm tra PostgreSQL đang chạy:
   ```cmd
   netstat -an | findstr 5432
   ```

2. Kiểm tra firewall không block port 5432

### Lỗi "role does not exist":
- Tạo lại user với đúng tên và password

## 6. Cấu hình .env

Sau khi setup thành công, đảm bảo file `.env` có:
```
ONCHAIN_DATABASE_URL=postgresql://onchain_user:Cuongnv123456@localhost:5432/bitcoin_onchain_signals
```

## 7. Test final

```cmd
# Trong thư mục onchain_intel_product
python -c "
import psycopg2
conn = psycopg2.connect('postgresql://onchain_user:Cuongnv123456@localhost:5432/bitcoin_onchain_signals')
print('✅ Database connection successful!')
conn.close()
"
```