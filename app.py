import streamlit as st
import asyncio
import os
import io

from google import genai
from openai import AsyncOpenAI

# 문서 파일 파싱용 라이브러리 (설치되어 있을 경우 자동 활성화)
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

st.set_page_page_config = st.set_page_config(page_title="Ultra AI 수업 & 파일 만능 분석기", layout="wide")
st.title("🎓 Ultra Multi-AI 만능 파일 분석 및 학습 솔루션")

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

# 파일 업로드 제한을 두지 않아 어떤 파일이든 업로드 가능
uploaded_file = st.file_uploader("📂 오디오, 동영상, PDF, Word, TXT, 소스코드 등 어떤 파일이든 업로드하세요", type=None)

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

if uploaded_file is not None:
    stt_text = ""
    file_name = uploaded_file.name
    file_ext = file_name.split(".")[-1].lower()
    file_bytes = uploaded_file.getvalue()

    # 1. 오디오 및 미디어 파일 처리 (Groq Whisper)
    audio_extensions = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm", "mp4", "mpeg", "mpga"]
    
    if file_ext in audio_extensions:
        if groq_client:
            with st.spinner(f"🎙️ 미디어 파일({file_ext})을 Groq Whisper AI로 초고속 음성 인식 중..."):
                try:
                    transcription = asyncio.run(groq_client.audio.transcriptions.create(
                        file=(file_name, file_bytes, f"audio/{file_ext}" if file_ext != "mp4" else "video/mp4"),
                        model="whisper-large-v3",
                        language="ko",
                        response_format="text"
                    ))
                    stt_text = str(transcription).strip()
                    st.success("✅ 음성/미디어 텍스트 변환(STT) 완료!")
                except Exception as e:
                    st.error(f"❌ 음성 변환 중 오류 발생: {e}")
        else:
            st.error("❌ GROQ_API_KEY가 필요합니다.")

    # 2. PDF 문서 파일 처리
    elif file_ext == "pdf":
        if HAS_PDF:
            with st.spinner("📄 PDF 문서 텍스트 추출 중..."):
                try:
                    reader = PdfReader(io.BytesIO(file_bytes))
                    extracted = [page.extract_text() for page in reader.pages if page.extract_text()]
                    stt_text = "\n".join(extracted)
                    st.success("✅ PDF 텍스트 추출 완료!")
                except Exception as e:
                    st.error(f"❌ PDF 읽기 오류: {e}")
        else:
            st.error("❌ pypdf 라이브러리가 설치되지 않았습니다.")

    # 3. Word(docx) 문서 파일 처리
    elif file_ext in ["docx", "doc"]:
        if HAS_DOCX:
            with st.spinner("📝 Word 문서 텍스트 추출 중..."):
                try:
                    doc = docx.Document(io.BytesIO(file_bytes))
                    extracted = [p.text for p in doc.paragraphs if p.text]
                    stt_text = "\n".join(extracted)
                    st.success("✅ Word 문서 읽기 완료!")
                except Exception as e:
                    st.error(f"❌ Word 읽기 오류: {e}")
        else:
            st.error("❌ python-docx 라이브러리가 설치되지 않았습니다.")

    # 4. 일반 텍스트 및 소스코드 파일 (TXT, C, C++, Python, MD, CSV 등)
    else:
        success = False
        for encoding in ["utf-8", "cp949", "euc-kr", "latin-1"]:
            try:
                stt_text = file_bytes.decode(encoding)
                success = True
                break
            except UnicodeDecodeError:
                continue
        
        if success:
            st.success(f"✅ 파일 로드 완료 ({file_ext.upper()} 형식)")
        else:
            st.error(f"❌ 파일의 인코딩을 읽을 수 없습니다. 지원되는 텍스트/미디어 형식이 맞는지 확인해주세요.")

    # 텍스트가 정상 추출/변환되었을 때 분석 버튼 활성화
    if stt_text:
        with st.expander("📄 추출/변환된 원본 내용 미리보기"):
            st.text(stt_text[:2000] + ("..." if len(stt_text) > 2000 else ""))

        if st.button("🚀 종합 학습 노트 & 예상 문제 생성", type="primary"):
            with st.spinner("🤖 다중 AI 엔진들이 데이터를 정밀 분석하고 있습니다..."):
                async def process_pipeline():
                    if ai_mode == "다중 AI 교차 검증 (권장)":
                        g_res, q_res = await asyncio.gather(
                            call_ai("Gemini", f"내용 요약:\n{stt_text}"),
                            call_ai("Groq", f"내용 요약:\n{stt_text}")
                        )
                        cross_p = f"[Gemini 요약]: {g_res}\n[Llama 요약]: {q_res}\n두 분석을 교차 검증하여 완성도 높은 노트로 정리해줘. 스타일: {note_style}"
                        final_note = await call_ai("Gemini", cross_p)
                    else:
                        engine_map = {
                            "Gemini 1.5 Flash": "Gemini", 
                            "Groq Llama 3.3": "Groq", 
                            "DeepSeek V3": "DeepSeek", 
                            "Cerebras Llama 3.1": "Cerebras",
                            "OpenRouter (Free Auto)": "OpenRouter"
                        }
                        final_note = await call_ai(engine_map[selected_single_ai], f"내용 요약 (스타일: {note_style}):\n{stt_text}")

                    dict_task = call_ai("Gemini", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개) 생성:\n{stt_text}")
                    exam_task = call_ai("Groq", f"시험/평가 예상 문제 4개(객관식 3, 서술형 1)와 정답/해설 작성:\n{stt_text}")
                    
                    dictionary, exam = await asyncio.gather(dict_task, exam_task)
                    return final_note, dictionary, exam

                note, dictionary, exam = asyncio.run(process_pipeline())
                st.session_state['note'] = note
                st.session_state['dict'] = dictionary
                st.session_state['exam'] = exam
                st.session_state['stt_text'] = stt_text

    if 'note' in st.session_state:
        t1, t2, t3, t4 = st.tabs(["📝 통합 요약 노트", "💡 용어 & 플래시카드", "🎯 예상 문제", "💬 AI Q&A 챗봇"])
        with t1:
            st.subheader("📌 교차 검증 요약 노트")
            st.markdown(st.session_state['note'])
        with t2:
            st.subheader("💡 주요 용어 및 암기 카드")
            st.markdown(st.session_state['dict'])
        with t3:
            st.subheader("🎯 출제 예상 문제")
            st.markdown(st.session_state['exam'])
        with t4:
            st.subheader("💬 AI 심화 Q&A 질문하기")
            q = st.text_input("자료 내용 중 이해가 안 되는 부분을 자유롭게 질문하세요:")
            if q:
                ans = asyncio.run(call_ai("Cerebras" if cerebras_key else "Gemini", f"자료 내용:{st.session_state['stt_text']}\n질문:{q}"))
                st.info(ans)
