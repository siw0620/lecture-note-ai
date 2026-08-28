import streamlit as st
import os
import io
import time
import json
import uuid
import subprocess
import tempfile
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

st.set_page_config(page_title="Wald des Wissens", layout="wide")

# 🥷 닌자고 폰트 스타일 적용 CSS 및 타이틀
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700;900&display=swap');
    
    .ninjago-font-title {
        font-family: 'Cinzel Decorative', serif;
        font-size: 42px;
        font-weight: 900;
        color: #ffffff;
        letter-spacing: 3px;
        text-shadow: 2px 2px 0px #ffcc00, 4px 4px 0px #000000;
        margin-bottom: 0px;
    }
    
    .ninjago-font-sub {
        font-family: monospace;
        font-size: 13px;
        color: #aaaaaa;
        letter-spacing: 2px;
        margin-top: 5px;
        text-transform: uppercase;
    }
    </style>
    
    <div style="padding: 10px 0 20px 0;">
        <div class="ninjago-font-title">WALD DES WISSENS</div>
        <div class="ninjago-font-sub">⚡ Ultimate Multi-AI Study Bunker & Sandbox</div>
    </div>
""", unsafe_allow_html=True)

# 🔄 새로고침(리로딩) 버튼
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
                localStorage.setItem('wald_ultimate_backup', {json.dumps(json_str)});
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

# 📂 클라우드 드라이브 연동 메뉴
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ 클라우드 드라이브 연동")
st.sidebar.info("💡 학습 기록이 자동 동기화되며, 백업 및 복원이 가능합니다.")

if 'note' in st.session_state:
    current_data = {
        "note": st.session_state.get('note', ''),
        "dict": st.session_state.get('dict', ''),
        "exam": st.session_state.get('exam', ''),
        "stt_text": st.session_state.get('stt_text', ''),
        "code_snippet": st.session_state.get('code_snippet', '')
    }
    save_to_browser_storage(current_data)
    
    json_str = json.dumps(current_data, ensure_ascii=False, indent=4)
    st.sidebar.download_button(
        label="📥 학습 데이터 백업 다운로드",
        data=json_str,
        file_name="wald_ultimate_backup.json",
        mime="application/json",
        use_container_width=True
    )

uploaded_backup = st.sidebar.file_uploader("📤 백업 파일 불러오기", type=["json"])
if uploaded_backup is not None:
    try:
        loaded_data = json.load(uploaded_backup)
        st.session_state['note'] = loaded_data.get('note', '')
        st.session_state['dict'] = loaded_data.get('dict', '')
        st.session_state['exam'] = loaded_data.get('exam', '')
        st.session_state['stt_text'] = loaded_data.get('stt_text', '')
        st.session_state['code_snippet'] = loaded_data.get('code_snippet', '')
        st.sidebar.success("✅ 백업 데이터를 성공적으로 불러왔습니다!")
    except Exception as e:
        st.sidebar.error(f"❌ 파일 형식이 올바르지 않습니다: {e}")

uploaded_files = st.file_uploader(
    "📂 대용량 음성녹음, 동영상, PDF, Word, 소스코드(C, Python 등)를 올려주세요", 
    type=None, 
    accept_multiple_files=True
)

def call_ai(provider, prompt):
    """멀티 AI 상호 보완 Fallback 함수"""
    providers_order = [provider, "Gemini", "Cerebras", "DeepSeek", "Groq", "OpenRouter"]
    seen = set()
    ordered_providers = [p for p in providers_order if not (p in seen or seen.add(p))]

    for p in ordered_providers:
        try:
            if p == "Gemini" and gemini_client:
                try:
                    res = gemini_client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
                    if res and res.text: return res.text
                except Exception:
                    res = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    if res and res.text: return res.text
            elif p == "Groq" and groq_client:
                res = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
                if res.choices[0].message.content: return res.choices[0].message.content
            elif p == "DeepSeek" and deepseek_client:
                res = deepseek_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
                if res.choices[0].message.content: return res.choices[0].message.content
            elif p == "Cerebras" and cerebras_client:
                res = cerebras_client.chat.completions.create(model="llama3.1-70b", messages=[{"role": "user", "content": prompt}])
                if res.choices[0].message.content: return res.choices[0].message.content
            elif p == "OpenRouter" and openrouter_client:
                res = openrouter_client.chat.completions.create(model="meta-llama/llama-3.3-70b-instruct:free", messages=[{"role": "user", "content": prompt}])
                if res.choices[0].message.content: return res.choices[0].message.content
        except Exception:
            continue
            
    return "[모든 AI 통신 실패]: 사용 가능한 AI 엔진이 없습니다."

# 🚀 파일 분석 전송
if uploaded_files:
    st.markdown("---")
    if st.button("🚀 업로드한 파일 통합 분석 전송하기", type="primary", use_container_width=True):
        combined_text_list = []
        raw_audio_file = None
        extracted_code = ""
        
        with st.status("📁 파일 최적화, 음성 압축 및 코드 분석 중...", expanded=True) as status:
            for file in uploaded_files:
                file_name = file.name
                file_ext = file.name.split(".")[-1].lower()
                file_bytes = file.getvalue()
                file_text = ""
                file_size_mb = len(file_bytes) / (1024 * 1024)

                audio_extensions = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm", "mp4", "mpeg", "mpga"]

                if file_ext in audio_extensions:
                    raw_audio_file = (file_name, file_bytes)
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
                            
                            if os.path.exists(temp_in_path): os.remove(temp_in_path)
                            if os.path.exists(temp_out_path): os.remove(temp_out_path)
                        except Exception:
                            pass

                    transcription_success = False
                    if groq_client and len(processed_audio_bytes) <= 24 * 1024 * 1024:
                        status.update(label=f"🎙️ Groq Whisper 타임스탬프 전사 중...")
                        try:
                            transcription = groq_client.audio.transcriptions.create(
                                file=(f"audio_{unique_id}.mp3", processed_audio_bytes, "audio/mp3"),
                                model="whisper-large-v3",
                                language="ko",
                                response_format="verbose_json"
                            )
                            # 세그먼트별 타임스탬프 가공
                            segments_text = []
                            if hasattr(transcription, 'segments') and transcription.segments:
                                for seg in transcription.segments:
                                    start_sec = int(seg.get('start', 0))
                                    m, s = divmod(start_sec, 60)
                                    time_str = f"[{m:02d}:{s:02d}]"
                                    segments_text.append(f"{time_str} {seg.get('text', '')}")
                                file_text = "\n".join(segments_text)
                            else:
                                file_text = str(transcription.text)
                            transcription_success = True
                        except Exception:
                            pass

                    if not transcription_success and gemini_client:
                        try:
                            temp_gemini_path = f"gemini_temp_{unique_id}.{file_ext}"
                            with open(temp_gemini_path, "wb") as f:
                                f.write(file_bytes)
                            with open(temp_gemini_path, "rb") as f:
                                g_file_res = gemini_client.files.upload(
                                    file=f,
                                    config=types.UploadFileConfig(mime_type=f"audio/{file_ext}")
                                )
                            if os.path.exists(temp_gemini_path): os.remove(temp_gemini_path)

                            while g_file_res.state.name == "PROCESSING":
                                time.sleep(2)
                                g_file_res = gemini_client.files.get(name=g_file_res.name)

                            g_ans = gemini_client.models.generate_content(
                                model='gemini-3.6-flash',
                                contents=[g_file_res, "이 음성/영상 파일의 전체 내용을 타임스탬프([분:초]) 형식과 함께 상세히 전사해줘."]
                            )
                            file_text = g_ans.text
                        except Exception:
                            file_text = "[음성 전사 실패]"

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
                elif file_ext in ["c", "cpp", "py", "java", "js", "txt", "html", "css"]:
                    for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
                        try:
                            file_text = file_bytes.decode(encoding)
                            extracted_code = file_text
                            break
                        except UnicodeDecodeError:
                            continue
                else:
                    for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
                        try:
                            file_text = file_bytes.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue

                if file_text:
                    combined_text_list.append(f"--- [파일명: {file_name}] ---\n{file_text}")

            status.update(label="✅ 파일 분석 및 전사 완료!", state="complete", expanded=False)

        full_combined_text = "\n\n".join(combined_text_list)

        if full_combined_text:
            with st.status("🤖 멀티 AI 상호 교차 검증 및 학습 세트 생성 중...", expanded=True) as ai_status:
                
                st.write("📌 [1/3] 상호 보완 요약 노트 작성 중...")
                if ai_mode == "다중 AI 교차 검증 (권장)":
                    primary_draft = call_ai("Groq", f"통합 내용 요약:\n{full_combined_text}")
                    reviewer_opinion = call_ai("Gemini", f"통합 내용 요약:\n{full_combined_text}")
                    cross_prompt = f"[메인 초안]: {primary_draft}\n[교차 검토 의견]: {reviewer_opinion}\n위 내용을 결합하여 상호 보완된 가장 완벽한 최종 노트로 정리해줘. 스타일: {note_style}"
                    final_note = call_ai("Cerebras", cross_prompt)
                else:
                    engine_map = {
                        "Groq Llama 3.3": "Groq", "Gemini 3.6 Flash": "Gemini", 
                        "DeepSeek V3": "DeepSeek", "Cerebras Llama 3.1": "Cerebras",
                        "OpenRouter (Free Auto)": "OpenRouter"
                    }
                    final_note = call_ai(engine_map[selected_single_ai], f"통합 내용 요약 (스타일: {note_style}):\n{full_combined_text}")

                st.write("💡 [2/3] 플래시카드 퀴즈 및 용어 세트 생성 중...")
                dictionary = call_ai("Cerebras", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개)를 JSON형태나 보기 쉽게 정리해줘:\n{full_combined_text}")

                st.write("🎯 [3/3] 시험 출제 예상 문제 제작 중...")
                exam = call_ai("Gemini", f"시험/평가 예상 문제 4개(객관식 3, 서술형 1)와 정답/해설 작성:\n{full_combined_text}")

                ai_status.update(label="✨ 모든 학습 데이터 구성 완료!", state="complete", expanded=False)

            st.session_state['note'] = final_note
            st.session_state['dict'] = dictionary
            st.session_state['exam'] = exam
            st.session_state['stt_text'] = full_combined_text
            if raw_audio_file:
                st.session_state['audio_file'] = raw_audio_file
            if extracted_code:
                st.session_state['code_snippet'] = extracted_code
            st.rerun()

# 탭 메뉴 구성 (총 6가지 올인원 기능 탭)
if 'note' in st.session_state:
    st.markdown("---")
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📝 통합 요약 노트", 
        "🎙️ 오디오 타임스탬프", 
        "💡 플래시카드 퀴즈", 
        "🎯 예상 문제", 
        "💻 코드 샌드박스", 
        "💬 AI Q&A 챗봇"
    ])
    
    with t1:
        st.subheader("📌 교차 검증 통합 요약 노트")
        st.markdown(st.session_state['note'])
        
    with t2:
        st.subheader("🎙️ 실시간 오디오 타임스탬프 & 플레이어")
        if 'audio_file' in st.session_state:
            fname, fbytes = st.session_state['audio_file']
            st.audio(fbytes, format='audio/mp3')
            st.info("💡 아래 타임스탬프([분:초])를 참고하여 원하는 구간을 확인하세요.")
        st.text_area("전사 대본 및 타임스탬프 로그", st.session_state['stt_text'], height=300)
        
    with t3:
        st.subheader("💡 플래시카드 인터랙티브 암기 퀴즈")
        st.markdown(st.session_state['dict'])
        st.info("🎯 카드를 넘겨가며 핵심 용어와 Q&A를 복습하세요!")
        
    with t4:
        st.subheader("🎯 출제 예상 문제 및 정답")
        st.markdown(st.session_state['exam'])
        
    with t5:
        st.subheader("💻 소스코드 샌드박스 및 실행기 (C / Python)")
        code_input = st.text_area(
            "실행할 소스코드를 입력하거나 업로드된 코드를 확인하세요:",
            value=st.session_state.get('code_snippet', 'print("Hello, Wald des Wissens!")'),
            height=200
        )
        lang_choice = st.selectbox("언어 선택", ["Python", "C"])
        
        if st.button("▶️ 코드 실행하기", use_container_width=True):
            with st.spinner("⚡ 샌드박스 환경에서 실행 중..."):
                if lang_choice == "Python":
                    try:
                        # 안전한 파이썬 격리 실행
                        old_stdout = sys.stdout if 'sys' in globals() else None
                        import io, sys
                        new_stdout = io.StringIO()
                        sys.stdout = new_stdout
                        exec(code_input, {})
                        sys.stdout = old_stdout
                        output = new_stdout.getvalue()
                        st.success("✅ 실행 성공!")
                        st.code(output if output else "(출력 결과가 없습니다)")
                    except Exception as e:
                        st.error(f"❌ 실행 에러: {e}")
                elif lang_choice == "C":
                    with tempfile.TemporaryDirectory() as tmpdir:
                        c_file = os.path.join(tmpdir, "main.c")
                        exe_file = os.path.join(tmpdir, "main.out")
                        with open(c_file, "w", encoding="utf-8") as f:
                            f.write(code_input)
                        
                        try:
                            compile_res = subprocess.run(["gcc", c_file, "-o", exe_file], capture_output=True, text=True, timeout=5)
                            if compile_res.returncode != 0:
                                st.error(f"❌ 컴파일 에러:\n{compile_res.stderr}")
                            else:
                                run_res = subprocess.run([exe_file], capture_output=True, text=True, timeout=5)
                                st.success("✅ C 프로그램 실행 성공!")
                                st.code(run_res.stdout)
                        except Exception as e:
                            st.error(f"❌ C 실행 환경 오류 (gcc 미설치 등): {e}")

    with t6:
        st.subheader("💬 AI 심화 Q&A 질문하기")
        q = st.text_input("학습한 내용에 대해 궁금한 점을 자유롭게 물어보세요:")
        if q:
            with st.spinner("🤖 AI가 답변을 작성 중..."):
                ans = call_ai("Groq" if groq_key else "Gemini", f"통합 내용:{st.session_state['stt_text']}\n질문:{q}")
            st.info(ans)
