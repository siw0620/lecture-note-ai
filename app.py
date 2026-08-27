import streamlit as st
import asyncio
import os
import requests
from google import genai
from openai import AsyncOpenAI

# 1. API 키 불러오기 (Secrets에 설정된 키 자동 매핑)
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")
deepseek_key = os.getenv("DEEPSEEK_API_KEY")
cerebras_key = os.getenv("CEREBRAS_API_KEY")
cohere_key = os.getenv("COHERE_API_KEY")
elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")

# 클라이언트 객체 생성 (키가 있는 경우에만 활성화)
gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
groq_client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key) if groq_key else None
openrouter_client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key) if openrouter_key else None
deepseek_client = AsyncOpenAI(base_url="https://api.deepseek.com", api_key=deepseek_key) if deepseek_key else None
cerebras_client = AsyncOpenAI(base_url="https://api.cerebras.ai/v1", api_key=cerebras_key) if cerebras_key else None

st.set_page_config(page_title="Ultra AI 수업 분석 솔루션 Pro", layout="wide")
st.title("🎓 Ultra Multi-AI 수업 분석 & 하드웨어 연동 시스템")

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

# 파일 업로드 (텍스트 또는 ESP32/스마트폰 오디오 WAV)
uploaded_file = st.file_uploader("수업 텍스트(.txt) 또는 자작 녹음기 오디오(.wav) 업로드", type=["txt", "wav"])

async def call_ai(provider, prompt):
    try:
        if provider == "Gemini" and gemini_client:
            res = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model='gemini-1.5-flash',
                contents=prompt
            )
            return res.text
        elif provider == "Groq" and groq_client:
            res = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content
        elif provider == "DeepSeek" and deepseek_client:
            res = await deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content
        elif provider == "Cerebras" and cerebras_client:
            res = await cerebras_client.chat.completions.create(
                model="llama3.1-70b",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content
        elif provider == "OpenRouter" and openrouter_client:
            res = await openrouter_client.chat.completions.create(
                model="meta-llama/llama-3.3-70b-instruct:free",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content
    except Exception as e:
        return f"[{provider} 통신 오류]: {str(e)}"
    return f"[{provider}] API 키가 미설정 상태입니다."

if uploaded_file is not None:
    stt_text = ""
    
    # WAV 오디오 파일 처리 (Groq Whisper STT 자동 구동)
    if uploaded_file.name.endswith(".wav"):
        if groq_client:
            with st.spinner("🎙️ 자작 녹음기 음성 파일(WAV)을 Groq Whisper로 텍스트 변환 중..."):
                try:
                    transcription = asyncio.run(groq_client.audio.transcriptions.create(
                        file=(uploaded_file.name, uploaded_file.getvalue(), "audio/wav"),
                        model="whisper-large-v3",
                        response_format="text"
                    ))
                    stt_text = transcription
                    st.success("✅ 음성 텍스트 변환(STT) 완료!")
                except Exception as e:
                    st.error(f"STT 변환 실패: {e}")
        else:
            st.error("WAV 음성 변환을 위해 GROQ_API_KEY가 필요합니다.")
    else:
        stt_text = uploaded_file.getvalue().decode("utf-8")

    if stt_text and st.button("🚀 종합 학습 노트 & 예상 문제 생성", type="primary"):
        with st.spinner("AI 엔진들이 수업 데이터를 정밀 분석 중입니다..."):
            
            async def process_pipeline():
                # 1. 수업 노트 요약
                if ai_mode == "다중 AI 교차 검증 (권장)":
                    g_res, q_res = await asyncio.gather(
                        call_ai("Gemini", f"수업 요약:\n{stt_text}"),
                        call_ai("Groq", f"수업 요약:\n{stt_text}")
                    )
                    cross_p = f"[Gemini 요약]: {g_res}\n[Llama 요약]: {q_res}\n두 분석을 교차 검증하여 일치하는 내용만 정리. 스타일: {note_style}"
                    final_note = await call_ai("Gemini", cross_p)
                else:
                    engine_map = {
                        "Gemini 1.5 Flash": "Gemini", 
                        "Groq Llama 3.3": "Groq", 
                        "DeepSeek V3": "DeepSeek", 
                        "Cerebras Llama 3.1": "Cerebras",
                        "OpenRouter (Free Auto)": "OpenRouter"
                    }
                    final_note = await call_ai(engine_map[selected_single_ai], f"수업 요약 (스타일: {note_style}):\n{stt_text}")

                # 2. 용어사전, 암기카드, 시험 예상 문제 생성
                dict_task = call_ai("Gemini", f"핵심 용어 5개 및 암기 플래시카드(Q&A 5개) 생성:\n{stt_text}")
                exam_task = call_ai("Groq", f"시험 예상 문제 4개(객관식3, 서술형1)와 정답/해설 작성:\n{stt_text}")
                
                dictionary, exam = await asyncio.gather(dict_task, exam_task)
                return final_note, dictionary, exam

            note, dictionary, exam = asyncio.run(process_pipeline())
            st.session_state['note'] = note
            st.session_state['dict'] = dictionary
            st.session_state['exam'] = exam
            st.session_state['stt_text'] = stt_text

    # 결과 UI 화면
    if 'note' in st.session_state:
        t1, t2, t3, t4, t5 = st.tabs(["📝 통합 요약 노트", "💡 용어 & 플래시카드", "🎯 예상 문제", "💬 AI Q&A 챗봇", "🔊 오디오 브리핑"])

        with t1:
            st.subheader("📌 교차 검증 수업 노트")
            st.markdown(st.session_state['note'])

        with t2:
            st.subheader("💡 주요 용어 및 암기 카드")
            st.markdown(st.session_state['dict'])

        with t3:
            st.subheader("🎯 출제 예상 문제")
            st.markdown(st.session_state['exam'])

        with t4:
            st.subheader("💬 AI 심화 Q&A 질문하기")
            q = st.text_input("수업 내용 중 이해가 안 되는 부분을 입력하세요:")
            if q:
                ans = asyncio.run(call_ai("DeepSeek" if deepseek_key else "Gemini", f"수업내용:{stt_text}\n질문:{q}"))
                st.info(ans)

        with t5:
            st.subheader("🔊 ElevenLabs 음성 브리핑")
            if st.button("요약 노트 음성(TTS) 듣기"):
                if elevenlabs_key:
                    st.info("ElevenLabs AI 음성 합성 중...")
                    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                    headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": elevenlabs_key}
                    data = {"text": st.session_state['note'][:500], "model_id": "eleven_monolingual_v1"}
                    response = requests.post(url, json=data, headers=headers)
                    if response.status_code == 200:
                        st.audio(response.content, format="audio/mp3")
                    else:
                        st.error("음성 합성 실패. API 키를 확인해 주세요.")
                else:
                    st.warning("ElevenLabs API 키가 필요합니다. Secrets에 ELEVENLABS_API_KEY를 추가하세요.")

        st.divider()
        full_result = f"# 요약노트\n{st.session_state['note']}\n\n# 용어 및 카드\n{st.session_state['dict']}\n\n# 예상문제\n{st.session_state['exam']}"
        st.download_button(label="📥 전체 학습 자료 패키지 (.txt) 다운로드", data=full_result, file_name="study_package.txt")
