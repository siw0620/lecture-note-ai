import streamlit as st
import asyncio
import os
import io

from google import genai
from openai import AsyncOpenAI

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
groq_client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key) if groq_key else None
openrouter_client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key) if openrouter_key else None
deepseek_client = AsyncOpenAI(base_url="https://api.deepseek.com", api_key=deepseek_key) if deepseek_key else None
cerebras_client = AsyncOpenAI(base_url="https://api.cerebras.ai/v1", api_key=cerebras_key) if cerebras_key else None

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

async def call_ai(provider, prompt):
    try:
        if provider == "Gemini" and gemini_client:
            res = await asyncio.to_thread(gemini_client.models.generate_content, model='gemini-1.5-flash', contents=prompt)
            return res.text
        elif provider == "Groq" and groq_client:
            res = await groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "DeepSeek" and deepseek_client:
            res = await deepseek_client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "Cerebras" and cerebras_client:
            res = await cerebras_client.chat.completions.create(model="llama3.1-70b", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
        elif provider == "OpenRouter" and openrouter_client:
            res = await openrouter_client.chat.completions.create(model="meta-llama/llama-3.3-70b-instruct:free", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content
    except Exception as e:
        return f"[{provider} 통신 오류]: {str(e)}"
    return f"[{provider}] API 키가 설정되지 않았습니다."

if uploaded_files:
    combined_text_list = []
    st.info(f"📁 총 {len(uploaded_files)}개의 파일이 업로드되었습니다. 처리 중...")

    for file in uploaded_files:
        file_name = file.name
        file_ext = file_name.split(".")[-1].lower()
        file_bytes = file.getvalue()
        file_text = ""
        file_size_mb = len(file_bytes) / (1024 * 1024)

        audio_extensions = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm", "mp4", "mpeg", "mpga"]

        # 1. 음성 및 미디어 파일 처리
        if file_ext in audio_extensions:
            if file_size_mb <= 25 and groq_client:
                with st.spinner(f"🎙️ '{file_name}' ({file_size_mb:.1f}MB) Groq Whisper 초고속 변환 중..."):
                    try:
                        transcription = asyncio.run(groq_client.audio.transcriptions.create(
                            file=(file_name, file_bytes, f"audio/{file_ext}" if file_ext != "mp4" else "video/mp4"),
                            model="whisper-large-v3",
                            language="ko",
                            response_format="text"
                        ))
                        file_text = str(transcription).strip()
                        st.success(f"✅ '{file_name}' Groq 변환 완료")
                    except Exception as e:
                        st.error(f"❌ '{file_name}' Groq 변환 오류: {e}")
            elif gemini_client:
                with st.spinner(f"🎙️ '{file_name}' ({file_size_mb:.1f}MB) 대용량 파일 Gemini 멀티모달 분석 중..."):
                    try:
                        mime_type = f"audio/{file_ext}" if file_ext != "mp4" else "video/mp4"
                        # 에러를 방지하기 위해 일반 동기 방식으로 Gemini 호출
                        res = gemini_client.models.generate_content(
                            model='gemini-1.5-flash',
                            contents=[
                                {"mime_type": mime_type, "data": file_bytes},
                                "이 음성/동영상 파일의 모든 대화 내용을 빠짐없이 한국어로 텍스트로 받아적어줘(STT)."
                            ]
                        )
                        file_text = res.text.strip()
                        st.success(f"✅ '{file_name}' Gemini 대용량 분석 완료")
                    except Exception as e:
                        st.error(f"❌ '{file_name}' Gemini 분석 오류: {e}")
            else:
                st.error("❌ API 키(GROQ_API_KEY 또는 GEMINI_API_KEY) 설정을 확인해주세요.")

        # 2. PDF 문서 파일
        elif file_ext == "pdf":
            if HAS_PDF:
                try:
                    reader = PdfReader(io.BytesIO(file_bytes))
                    extracted = [page.extract_text() for page in reader.pages if page.extract_text()]
                    file_text = "\n".join(extracted)
                    st.success(f"✅ '{file_name}' PDF 추출 완료")
                except Exception as e:
                    st.error(f"❌ '{file_name}' 읽기 오류: {e}")
            else:
                st.error("❌ pypdf 라이브러리가 필요합니다.")

        # 3. Word 문서 파일
        elif file_ext in ["docx", "doc"]:
            if HAS_DOCX:
                try:
                    doc = docx.Document(io.BytesIO(file_bytes))
                    extracted = [p.text for p in doc.paragraphs if p.text]
                    file_text = "\n".join(extracted)
                    st.success(f"✅ '{file_name}' Word 추출 완료")
                except Exception as e:
                    st.error(f"❌ '{file_name}' 읽기 오류: {e}")
            else:
                st.error("❌ python-docx 라이브러리가 필요합니다.")

        # 4. 일반 텍스트 및 소스코드 파일
        else:
            for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
                try:
                    file_text = file_bytes.decode(encoding)
                    st.success(f"✅ '{file_name}' 파일 읽기 완료")
                    break
                except UnicodeDecodeError:
                    continue

        if file_text:
            combined_text_list.append(f"--- [파일명: {file_name}] ---\n{file_text}")

    full_combined_text = "\n\n".join(combined_text_list)

    if full_combined_text:
        with st.expander("📄 추출된 전체 파일 통합 텍스트 확인"):
            st.text_area("통합 데이터 내용", full_combined_text, height=200)

        if st.button("🚀 전체 파일 통합 AI 학습 노트 생성", type="primary"):
            with st.spinner("🤖 AI가 업로드된 모든 파일의 데이터 분석 중..."):
                async def process_pipeline():
                    if ai_mode == "다중 AI 교차 검증 (권장)":
                        g_res, q_res = await asyncio.gather(
                            call_ai("Gemini", f"통합 내용 요약:\n{full_combined_text}"),
                            call_ai("Groq", f"통합 내용 요약:\n{full_combined_text}")
                        )
                        cross_p = f"[Gemini 요약]: {g_res}\n[Llama 요약]: {q_res}\n두 분석을 교차 검증하여 깔끔한 노트로 정리해줘. 스타일: {note_style}"
                        final_note = await call_ai("Gemini", cross_p)
                    else:
                        engine_map = {
                            "Gemini 1.5 Flash": "Gemini", 
                            "Groq Llama 3.3": "Groq", 
                            "DeepSeek V3": "DeepSeek", 
                            "Cerebras Llama 3.1": "Cerebras",
                            "OpenRouter (Free Auto)": "OpenRouter"
                        }
                        final_note = await call_ai(engine_map[selected_single_ai], f"통합 내용 요약 (스타일: {note_style}):\n{full_combined_text}")

                    dict_task = call_ai("Gemini", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개) 생성:\n{full_combined_text}")
                    exam_task = call_ai("Groq", f"시험/평가 예상 문제 4개(객관식 3, 서술형 1)와 정답/해설 작성:\n{full_combined_text}")
                    
                    dictionary, exam = await asyncio.gather(dict_task, exam_task)
                    return final_note, dictionary, exam

                note, dictionary, exam = asyncio.run(process_pipeline())
                st.session_state['note'] = note
                st.session_state['dict'] = dictionary
                st.session_state['exam'] = exam
                st.session_state['stt_text'] = full_combined_text

    if 'note' in st.session_state:
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
                ans = asyncio.run(call_ai("Cerebras" if cerebras_key else "Gemini", f"통합 내용:{st.session_state['stt_text']}\n질문:{q}"))
                st.info(ans)
