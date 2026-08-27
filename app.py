import streamlit as st
import os
import io

from google import genai
from openai import OpenAI

# 문서 파일 파싱용 라이브러리
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

# 사이드바 설정
st.sidebar.header("⚙️ AI 엔진 및 요약 설정")
ai_mode = st.sidebar.radio("분석 모드", ["다중 AI 교차 검증 (권장)", "단일 AI 신속 분석"])

selected_single_ai = "Gemini 1.5 Flash"
if ai_mode == "단일 AI 신속 분석":
    selected_single_ai = st.sidebar.selectbox(
        "사용할 AI 모델 선택",
        ["Gemini 1.5 Flash", "Groq Llama 3.3", "DeepSeek V3", "Cerebras Llama 3.1", "OpenRouter (Free Auto)"]
    )

note_style = st.sidebar.selectbox(
    "노트 정리 스타일",
    ["개조식 핵심 요약 (-함/-습 체)", "스토리텔링 친절한 설명형", "시험 직전 1분 요약형"]
)

# 다중 파일 업로드 허용
uploaded_files = st.file_uploader(
    "📂 대용량 음성녹음, 동영상, PDF, Word, 소스코드 등을 한번에 올려주세요 (25MB 초과 파일 자동 대응)", 
    type=None, 
    accept_multiple_files=True
)

def call_ai(provider, prompt):
    try:
        if provider == "Gemini" and gemini_client:
            res = gemini_client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
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

if uploaded_files:
    combined_text_list = []
    
    # 업로드된 파일 파싱 과정도 로딩 표시 추가
    with st.status("📁 파일 읽기 및 음성 변환 중...", expanded=True) as status:
        for file in uploaded_files:
            file_name = file.name
            file_ext = file_name.split(".")[-1].lower()
            file_bytes = file.getvalue()
            file_text = ""
            file_size_mb = len(file_bytes) / (1024 * 1024)

            audio_extensions = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm", "mp4", "mpeg", "mpga"]

            if file_ext in audio_extensions:
                if file_size_mb <= 25 and groq_client:
                    status.update(label=f"🎙️ '{file_name}' ({file_size_mb:.1f}MB) Groq Whisper 초고속 변환 중...")
                    try:
                        transcription = groq_client.audio.transcriptions.create(
                            file=(file_name, file_bytes, f"audio/{file_ext}" if file_ext != "mp4" else "video/mp4"),
                            model="whisper-large-v3",
                            language="ko",
                            response_format="text"
                        )
                        file_text = str(transcription).strip()
                    except Exception as e:
                        st.error(f"❌ '{file_name}' Groq 변환 오류: {e}")
                elif gemini_client:
                    status.update(label=f"🎙️ '{file_name}' ({file_size_mb:.1f}MB) 대용량 파일 Gemini 멀티모달 분석 중...")
                    try:
                        mime_type = f"audio/{file_ext}" if file_ext != "mp4" else "video/mp4"
                        res = gemini_client.models.generate_content(
                            model='gemini-1.5-flash',
                            contents=[
                                {"mime_type": mime_type, "data": file_bytes},
                                "이 음성/동영상 파일의 모든 대화 내용을 빠짐없이 한국어로 텍스트로 받아적어줘(STT)."
                            ]
                        )
                        file_text = res.text.strip()
                    except Exception as e:
                        st.error(f"❌ '{file_name}' Gemini 분석 오류: {e}")
                else:
                    st.error("❌ API 키 설정을 확인해주세요.")

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

        status.update(label="✅ 모든 파일 처리 완료!", state="complete", expanded=False)

    full_combined_text = "\n\n".join(combined_text_list)

    if full_combined_text:
        with st.expander("📄 추출된 전체 파일 통합 텍스트 확인"):
            st.text_area("통합 데이터 내용", full_combined_text, height=200)

        # 🚀 눈에 띄는 명확한 전송 버튼 생성
        st.markdown("---")
        if st.button("🚀 전체 파일 통합 AI 학습 노트 및 문제 생성하기", type="primary", use_container_width=True):
            
            # 단계별 로딩 상태바 (Progress / Status)
            with st.status("🤖 AI 엔진들이 데이터를 정밀 분석하고 있습니다...", expanded=True) as ai_status:
                
                st.write("📌 [1/3] 핵심 요약 노트 및 교차 검증 중...")
                if ai_mode == "다중 AI 교차 검증 (권장)":
                    g_res = call_ai("Gemini", f"통합 내용 요약:\n{full_combined_text}")
                    q_res = call_ai("Groq", f"통합 내용 요약:\n{full_combined_text}")
                    cross_p = f"[Gemini 요약]: {g_res}\n[Llama 요약]: {q_res}\n두 분석을 교차 검증하여 깔끔한 노트로 정리해줘. 스타일: {note_style}"
                    final_note = call_ai("Gemini", cross_p)
                else:
                    engine_map = {
                        "Gemini 1.5 Flash": "Gemini", 
                        "Groq Llama 3.3": "Groq", 
                        "DeepSeek V3": "DeepSeek", 
                        "Cerebras Llama 3.1": "Cerebras",
                        "OpenRouter (Free Auto)": "OpenRouter"
                    }
                    final_note = call_ai(engine_map[selected_single_ai], f"통합 내용 요약 (스타일: {note_style}):\n{full_combined_text}")

                st.write("💡 [2/3] 핵심 용어 및 플래시카드 생성 중...")
                dictionary = call_ai("Gemini", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개) 생성:\n{full_combined_text}")

                st.write("🎯 [3/3] 시험 출제 예상 문제 제작 중...")
                exam = call_ai("Groq", f"시험/평가 예상 문제 4개(객관식 3, 서술형 1)와 정답/해설 작성:\n{full_combined_text}")

                ai_status.update(label="✨ 모든 분석 및 노트 생성이 완료되었습니다!", state="complete", expanded=False)

            # 세션에 결과 저장
            st.session_state['note'] = final_note
            st.session_state['dict'] = dictionary
            st.session_state['exam'] = exam
            st.session_state['stt_text'] = full_combined_text
            st.rerun() # 화면 새로고침하여 결과 탭 출력

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
                    ans = call_ai("Cerebras" if cerebras_key else "Gemini", f"통합 내용:{st.session_state['stt_text']}\n질문:{q}")
                st.info(ans)
