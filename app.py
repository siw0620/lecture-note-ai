import streamlit as st
import asyncio
import os
from google import genai
from openai import AsyncOpenAI

# API 키 설정
gemini_key = os.getenv("GEMINI_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

gemini_client = genai.Client(api_key=gemini_key)
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=groq_key
)

st.title("🎓 Multi-AI 교차 검증 수업 노트")

uploaded_file = st.file_uploader("삼성 음성녹음 텍스트(.txt) 또는 음성(.wav) 업로드", type=["txt", "wav"])

if uploaded_file is not None:
    st.info("AI가 수업 내용을 교차 검증 중입니다...")
    
    if uploaded_file.name.endswith(".txt"):
        stt_text = uploaded_file.getvalue().decode("utf-8")
    else:
        stt_text = "Groq Whisper STT 변환 텍스트"

    async def process_verification(text):
        # Gemini 1차 요약
        gemini_res = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=f"수업 핵심 요약:\n{text}"
        ).text

        # Groq Llama 3.3 1차 요약
        groq_res = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"수업 핵심 요약:\n{text}"}]
        )
        llama_res = groq_res.choices[0].message.content

        # 교차 검증
        cross_prompt = f"""
        [Gemini 분석]: {gemini_res}
        [Llama 분석]: {llama_res}
        
        두 AI의 분석 중 공통으로 일치하는 핵심 개념만 추출하여 정돈된 수업 노트로 만들어줘.
        """
        final_res = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=cross_prompt
        ).text
        
        return final_res

    result = asyncio.run(process_verification(stt_text))
    st.subheader("📌 최종 교차 검증 수업 노트")
    st.markdown(result)
