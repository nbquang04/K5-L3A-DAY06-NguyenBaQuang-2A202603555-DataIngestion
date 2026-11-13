# Thực hiện bài với Think Python 2e

Đã chuẩn bị corpus PDF gồm 50 trang nội dung (chương 8–12), manifest và 20 câu benchmark. Bộ câu hỏi do AI soạn và kiểm tra quote với text trích xuất; học viên cần đối chiếu PDF. Không coi các nhãn AI là chấm thủ công của học viên.

## Chạy từ thư mục gốc bằng PowerShell

```powershell
cd starter
.\.venv\Scripts\python.exe scripts/check_setup.py
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.run --split dev
```

Lần đầu tải model `sentence-transformers/all-MiniLM-L6-v2` cần mạng; cache ở `.cache/models` trong thư mục gốc. Model chạy CPU, 384 chiều, cùng cách encode và normalize cho query/document. Không cần API key; chi phí API bằng 0, chưa đo điện/khấu hao máy.

Sau khi dev hoàn tất, `results/selection.json` ghi lựa chọn dựa trên Hit@3 dev, rồi Hit@1, rồi số chunk; sau đó mới chạy:

```powershell
.\.venv\Scripts\python.exe -m src.run --split test
```

Không sửa cấu hình theo kết quả test. Mọi lỗi backend/model được báo và ghi `results/errors.log`; không có mock fallback.

## Dữ liệu và chiến lược

PDF gốc: `data/raw/thinkpython2.pdf`. Manifest: `data/manifest.json`. Corpus đã chuẩn hóa theo layout: `data/processed/corpus.json`. `data/processed/pages.json` là kết quả script inspect ban đầu, không dùng để benchmark.

Nguồn: Allen B. Downey, [Think Python, 2nd Edition, Version 2.4.1](https://greenteapress.com/thinkpython2/thinkpython2.pdf). Giấy phép: [CC BY-NC 3.0](https://creativecommons.org/licenses/by-nc/3.0/). Chỉ dùng phi thương mại, giữ tác giả và giấy phép. Thay đổi: trích chương 8–12, loại trang có ít hơn 500 ký tự không trắng, chuẩn hóa Unicode/khoảng trắng và chia chunk. Ngày snapshot và SHA-256 có trong manifest; đây là thời gian file được lưu, không phải ngày hiệu lực tài liệu.

Trang là số trang vật lý PDF bắt đầu từ 1. Metadata chương lấy từ ranh giới chương đã đối chiếu text. Tổng 50 trang; trang gần như chỉ có header bị loại. Lỗi font italic, tách từ, ngắt dòng, code indentation và hình vẽ là giới hạn; không tự sửa nội dung không chắc chắn. Sách phản ánh Python thời điểm xuất bản, không được dùng để khẳng định hành vi Python mới nhất.

A: chunk 500 ký tự, overlap 50. B: theo đoạn có dòng trống, tối đa 1000 ký tự, tách dòng khi đoạn quá dài. C: dùng nguyên vector/chunk B và chỉ lọc `chapter` khi câu hỏi cung cấp. Chunk không vượt trang; ngữ cảnh qua trang có thể mất. Store pgvector truy xuất cosine exact, không tạo ANN index. B/C dùng chung snapshot database để đảm bảo chỉ thay filter. Mỗi snapshot được thay nguyên tử trong transaction, xóa chunk cũ; dev ghi hai lần và kiểm tra số lượng không tăng.

Benchmark: 15 dev / 5 test; q05, q11, q16 có filter. Quote đã kiểm tra tồn tại trong corpus. Cùng nguồn và chủ đề ở hai split nên có nguy cơ rò rỉ theo chủ đề; chỉ là thử nghiệm nhỏ. `benchmark/protocol.json` ghi hash và tiêu chí chọn trước test. Không đưa gold vào embedding query hay filter.

## Kết quả và phần cần chấm

- `results/traces_dev.json`, `traces_test.json`: top-3 đầy đủ, score cosine và metadata.
- `results/metrics_*.json`: Hit@1, Evidence Hit@3 dạng số đúng/tổng và tỷ lệ. Đây là proxy exact evidence sau bỏ whitespace; cần rà soát evidence tương đương và nguồn hợp lệ khác.
- `results/ingestion_stats.json`: số chunk, độ dài, token, thời gian embedding + hai lần ghi DB, kiểm tra nạp trùng và số chunk bị model truncation.
- `results/run_*.json`: timestamp, phiên bản thư viện, model revision, runtime và chi phí.
- `results/audit_coherence.csv`: cùng 10 trang đầu, vị trí giữa trang, mọi chunk phủ vị trí đó. Chấm 0/1/2 và lý do; nếu nhiều chunk mỗi vị trí, lấy trung bình trong vị trí trước rồi trung bình 10 vị trí.
- `results/audit_grounding.csv`: chấm top-3 cho từng câu test, 0 = không có evidence, 1 = thiếu điều kiện/ngữ cảnh, 2 = đủ trả lời và truy nguồn.
- `results/audit_metadata.csv`: đối chiếu từng hit với PDF; điền đủ/đúng và tuân thủ filter. Không có câu filter thì báo N/A.

Các bảng audit đã được Codex AI đánh giá từng trường hợp, có điểm, lý do và người chấm; tổng hợp trong results/audit_summary.json. Grounding/coherence dựa trên đọc nội dung, metadata được kiểm tra lại với PDF nguồn; không lấy exact-match làm điểm định tính. Quảng đã xác nhận các nhãn do AI hỗ trợ đề xuất. Quá trình này chưa phải đánh giá mù hoặc có người chấm độc lập. Lần chạy lại không ghi đè sheet hiện có; nếu thay corpus/cấu hình phải lưu audit cũ rồi tạo mẫu mới.

## Hoàn thiện nộp bài

Điền thông tin thật vào STUDENT.md, xem artifacts/experiment_log.csv, điền báo cáo report/individual/2A202603555_NguyenBaQuang.md. Không nộp .venv, .env, .cache hoặc API key. Đọc SUBMISSION.md trước khi nộp.

## Log nguồn và phiên bản model

Log kiểm tra lại từng trang: [page_processing_log.csv](results/page_processing_log.csv), tổng hợp: [page_processing_summary.json](results/page_processing_summary.json). Đây là kiểm tra lại sau benchmark, không phải log thời gian ingest ban đầu. Chạy từ thư mục gốc: "python starter/scripts/check_source_pages.py" bằng môi trường đã cài dependencies.

Model được cố định revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41. [model_provenance.json](results/model_provenance.json) ghi nguồn xác minh từ cache, hash file và so sánh vector mẫu A/B. Revision trong log cũ được bổ sung sau chạy; timestamp và metric gốc không thay đổi.
