import streamlit as st
import os
import io
import time
import json
import uuid
import streamlit.components.v1 as components

from google import genai
from google.genai import types
from openai import OpenAI

# 음성 압축용 pydub 라이브러리 및 문서 라이브러리 확인
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    from pypdf import PdfReader
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# 1. API 키 불러오기
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
cerebras_key = os.getenv("CEREBRAS_API_KEY")

# 클라이언트 초기화
gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key) if groq_key else None
openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key) if openrouter_key else None
deepseek_client = OpenAI(base_url="https://api.deepseek.com", api_key=deepseek_key) if deepseek_key else None
cerebras_client = OpenAI(base_url="https://api.cerebras.ai/v1", api_key=cerebras_key) if cerebras_key else None

st.set_page_config(page_title="Ultra AI 수업 & 대용량 파일 만능 분석기", layout="wide")
st.title("🎓 Ultra Multi-AI 대용량 파일 통합 분석 시스템")

# 🔄 새로고침(리로딩) 버튼 기능 구현
if st.sidebar.button("🔄 파일 및 화면 리로딩 (초기화)", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.markdown("---")

# ☁️ 브라우저 로컬 저장소 연동 자바스크립트 컴포넌트
def save_to_browser_storage(data_dict):
    json_str = json.dumps(data_dict, ensure_ascii=False)
    components.html(f"""
        <script>
            try {{
                localStorage.setItem('ultra_ai_drive_backup', {json.dumps(json_str)});
            }} catch (e) {{
                console.error("Storage save failed", e);
            }}
        </script>
    """, height=0, width=0)

# 사이드바 설정
st.sidebar.header("⚙️ AI 엔진 및 요약 설정")
ai_mode = st.sidebar.radio("분석 모드", ["다중 AI 교차 검증 (권장)", "단일 AI 신속 분석"])

selected_single_ai = "Groq Llama 3.3"
if ai_mode == "단일 AI 신속 분석":
    selected_single_ai = st.sidebar.selectbox(
        "사용할 AI 모델 선택",
        ["Groq Llama 3.3", "Gemini 3.6 Flash", "DeepSeek V3", "Cerebras Llama 3.1", "OpenRouter (Free Auto)"]
    )

note_style = st.sidebar.selectbox(
    "노트 정리 스타일",
    ["개조식 핵심 요약 (-함/-습 체)", "스토리텔링 친절한 설명형", "시험 직전 1분 요약형"]
)

# 📂 사이드바에 클라우드 드라이브 연동 메뉴 추가
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ 클라우드 드라이브 연동")
st.sidebar.info("💡 브라우저에 학습 기록이 자동 저장되며, 언제든 백업/복원할 수 있습니다.")

if 'note' in st.session_state:
    current_data = {
        "note": st.session_state.get('note', ''),
        "dict": st.session_state.get('dict', ''),
        "exam": st.session_state.get('exam', ''),
        "stt_text": st.session_state.get('stt_text', '')
    }
    save_to_browser_storage(current_data)
    
    json_str = json.dumps(current_data, ensure_ascii=False, indent=4)
    st.sidebar.download_button(
        label="📥 구글 드라이브 백업 파일 다운로드",
        data=json_str,
        file_name="google_drive_study_backup.json",
        mime="application/json",
        use_container_width=True
    )

uploaded_backup = st.sidebar.file_uploader("📤 드라이브 백업 파일 불러오기", type=["json"])
if uploaded_backup is not None:
    try:
        loaded_data = json.load(uploaded_backup)
        st.session_state['note'] = loaded_data.get('note', '')
        st.session_state['dict'] = loaded_data.get('dict', '')
        st.session_state['exam'] = loaded_data.get('exam', '')
        st.session_state['stt_text'] = loaded_data.get('stt_text', '')
        st.sidebar.success("✅ 클라우드 기록을 성공적으로 동기화했습니다!")
    except Exception as e:
        st.sidebar.error(f"❌ 파일 형식이 올바르지 않습니다: {e}")

# 다중 파일 업로드 허용
uploaded_files = st.file_uploader(
    "📂 대용량 음성녹음, 동영상, PDF, Word, 소스코드 등을 한번에 올려주세요 (대용량 음성 자동 압축 탑재)", 
    type=None, 
    accept_multiple_files=True
)

def call_ai(provider, prompt):
    try:
        if provider == "Gemini" and gemini_client:
            # 💡 최신 권장 모델 gemini-3.6-flash 적용
            try:
                res = gemini_client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                return res.text
            except Exception:
                res = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                return res.text
        elif provider == "Groq" and groq_client:
            res = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "DeepSeek" and deepseek_client:
            res = deepseek_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "Cerebras" and cerebras_client:
            res = cerebras_client.chat.completions.create(model="llama3.1-70b", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "OpenRouter" and openrouter_client:
            res = openrouter_client.chat.completions.create(model="meta-llama/llama-3.3-70b-instruct:free", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
    except Exception as e:
        return f"[{provider} 통신 오류]: {str(e)}"
    return f"[{provider}] API 키가 설정되지 않았습니다."

# 🚀 파일이 업로드된 상태에서 전송 버튼을 눌렀을 때만 분석 시작
if uploaded_files:
    st.markdown("---")
    if st.button("🚀 업로드한 파일 분석 전송하기", type="primary", use_container_width=True):
        combined_text_list = []
        
        with st.status("📁 파일 읽기, 용량 최적화 및 음성 분석 중...", expanded=True) as status:
            for file in uploaded_files:
                file_name = file.name
                file_ext = file.name.split(".")[-1].lower()
                file_bytes = file.getvalue()
                file_text = ""
                file_size_mb = len(file_bytes) / (1024 * 1024)

                audio_extensions = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm", "mp4", "mpeg", "mpga"]

                if file_ext in audio_extensions:
                    processed_audio_bytes = file_bytes
                    unique_id = uuid.uuid4().hex[:8]
                    
                    if HAS_PYDUB:
                        status.update(label=f"🗜️ '{file_name}' ({file_size_mb:.1f}MB) 고효율 오디오 압축 중...")
                        try:
                            temp_in_path = f"input_{unique_id}.{file_ext}"
                            temp_out_path = f"compressed_{unique_id}.mp3"
                            
                            with open(temp_in_path, "wb") as f:
                                f.write(file_bytes)
                            
                            audio = AudioSegment.from_file(temp_in_path)
                            audio = audio.set_channels(1)
                            audio = audio.set_frame_rate(16000)
                            audio.export(temp_out_path, format="mp3", bitrate="24k")
                            
                            with open(temp_out_path, "rb") as f:
                                processed_audio_bytes = f.read()
                            
                            compressed_size_mb = len(processed_audio_bytes) / (1024 * 1024)
                            status.update(label=f"✨ '{file_name}' 압축 성공! ({file_size_mb:.1f}MB ➔ {compressed_size_mb:.1f}MB)")
                            
                            if os.path.exists(temp_in_path): os.remove(temp_in_path)
                            if os.path.exists(temp_out_path): os.remove(temp_out_path)
                            file_size_mb = compressed_size_mb
                        except Exception as ex:
                            status.update(label=f"⚠️ pydub 압축 스킵: {ex}")

                    transcription_success = False
                    
                    # 1차 시도: Groq Whisper 이용
                    if groq_client and len(processed_audio_bytes) <= 24 * 1024 * 1024:
                        status.update(label=f"🎙️ '{file_name}' Groq Whisper 변환 중...")
                        try:
                            transcription = groq_client.audio.transcriptions.create(
                                file=(f"audio_{unique_id}.mp3", processed_audio_bytes, "audio/mp3"),
                                model="whisper-large-v3",
                                language="ko",
                                response_format="text"
                            )
                            file_text = str(transcription).strip()
                            transcription_success = True
                        except Exception as e:
                            st.warning(f"⚠️ Groq 변환 제한 초과/에러 발생, Gemini 우회 분석으로 전환합니다: {e}")

                    # 2차 시도: Gemini 멀티모달 분석 우회 (`gemini-3.6-flash` 사용)
                    if not transcription_success and gemini_client:
                        status.update(label=f"🔄 '{file_name}' 파일을 Gemini 대용량 멀티모달 분석 방식으로 우회 전사 중...")
                        try:
                            temp_gemini_path = f"gemini_temp_{unique_id}.{file_ext}"
                            with open(temp_gemini_path, "wb") as f:
                                f.write(file_bytes)
                            
                            with open(temp_gemini_path, "rb") as f:
                                g_file_res = gemini_client.files.upload(
                                    file=f,
                                    config=types.UploadFileConfig(mime_type=f"audio/{file_ext}")
                                )
                            
                            if os.path.exists(temp_gemini_path):
                                os.remove(temp_gemini_path)

                            while g_file_res.state.name == "PROCESSING":
                                time.sleep(2)
                                g_file_res = gemini_client.files.get(name=g_file_res.name)

                            g_ans = gemini_client.models.generate_content(
                                model='gemini-3.6-flash',
                                contents=[g_file_res, "이 음성/영상 파일의 전체 내용을 빠짐없이 한국어 텍스트로 상세히 전사(STT)해줘."]
                            )
                            file_text = g_ans.text
                            transcription_success = True
                            st.success(f"✅ '{file_name}' Gemini 우회 전사 완료!")
                        except Exception as ge:
                            st.error(f"❌ Gemini 우회 전사 실패: {ge}")

                elif file_ext == "pdf":
                    if HAS_PDF:
                        reader = PdfReader(io.BytesIO(file_bytes))
                        extracted = [page.extract_text() for page in reader.pages if page.extract_text()]
                        file_text = "\n".join(extracted)
                elif file_ext in ["docx", "doc"]:
                    if HAS_DOCX:
                        doc = docx.Document(io.BytesIO(file_bytes))
                        extracted = [p.text for p in doc.paragraphs if p.text]
                        file_text = "\n".join(extracted)
                else:
                    for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
                        try:
                            file_text = file_bytes.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue

                if file_text:
                    combined_text_list.append(f"--- [파일명: {file_name}] ---\n{file_text}")

            status.update(label="✅ 모든 파일 최적화 및 처리 완료!", state="complete", expanded=False)

        full_combined_text = "\n\n".join(combined_text_list)

        if full_combined_text:
            with st.status("🤖 Groq 메인 초안 작성 및 멀티 AI 교차 검증 중...", expanded=True) as ai_status:
                
                st.write("📌 [1/3] Groq 초안 작성 및 타 AI 교차 검증 진행 중...")
                if ai_mode == "다중 AI 교차 검증 (권장)":
                    q_res = call_ai("Groq", f"통합 내용 요약:\n{full_combined_text}")
                    g_res = call_ai("Gemini", f"통합 내용 요약:\n{full_combined_text}")
                    cross_p = f"[Groq 메인 초안]: {q_res}\n[Gemini 검토 의견]: {g_res}\n위 내용을 바탕으로 Groq의 분석을 중심으로 하되 Gemini의 의견을 반영하여 상호 교차 검증된 가장 완벽한 최종 노트로 정리해줘. 스타일: {note_style}"
                    final_note = call_ai("Groq", cross_p)
                else:
                    engine_map = {
                        "Groq Llama 3.3": "Groq", 
                        "Gemini 3.6 Flash": "Gemini", 
                        "DeepSeek V3": "DeepSeek", 
                        "Cerebras Llama 3.1": "Cerebras",
                        "OpenRouter (Free Auto)": "OpenRouter"
                    }
                    final_note = call_ai(engine_map[selected_single_ai], f"통합 내용 요약 (스타일: {note_style}):\n{full_combined_text}")

                st.write("💡 [2/3] 핵심 용어 및 플래시카드 생성 중...")
                dictionary = call_ai("Groq", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개) 생성:\n{full_combined_text}")

                st.write("🎯 [3/3] 시험 출제 예상 문제 제작 중...")
                exam = call_ai("Groq", f"시험/평가 예상 문제 4개(객관식 3, 서술형 1)와 정답/해설 작성:\n{full_combined_text}")

                ai_status.update(label="✨ Groq 중심 분석 및 교차 검증이 완료되었습니다!", state="complete", expanded=False)

            st.session_state['note'] = final_note
            st.session_state['dict'] = dictionary
            st.session_state['exam'] = exam
            st.session_state['stt_text'] = full_combined_text
            st.rerun()

if 'note' in st.session_state:
    st.markdown("---")
    t1, t2, t3, t4 = st.tabs(["📝 통합 요약 노트", "💡 용어 & 플래시카드", "🎯 예상 문제", "💬 AI Q&A 챗봇"])
    with t1:
        st.subheader("📌 교차 검증 통합 노트")
        st.markdown(st.session_state['note'])
    with t2:
        st.subheader("💡 주요 용어 및 암기 카드")
        st.markdown(st.session_state['dict'])
    with t3:
        st.subheader("🎯 출제 예상 문제")
        st.markdown(st.session_state['exam'])
    with t4:
        st.subheader("💬 AI 심화 Q&A 질문하기")
        q = st.text_input("통합 파일 내용에 대한 질문을 자유롭게 입력하세요:")
        if q:
            with st.spinner("🤖 AI가 답변을 작성하는 중..."):
                ans = call_ai("Groq" if groq_key else "Gemini", f"통합 내용:{st.session_state['stt_text']}\n질문:{q}")
            st.info(ans)
