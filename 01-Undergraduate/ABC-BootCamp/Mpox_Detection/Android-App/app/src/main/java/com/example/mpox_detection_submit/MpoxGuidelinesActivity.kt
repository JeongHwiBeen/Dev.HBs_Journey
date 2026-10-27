package com.example.mpox_detection_submit

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MpoxGuidelinesActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_mpox_guidelines)

        val guidelinesTextView = findViewById<TextView>(R.id.guidelinesTextView)

        // 행동 요령 내용을 여기에 설정
        val guidelines = """
            이미지 분류 결과만으로 엠폭스 감염 여부를 확정할 수 없습니다.
            
            1. 즉시 의료 전문가에게 연락하세요.
            2. 다른 사람과의 접촉을 피하세요.
            3. 마스크를 착용하고, 피부 발진을 덮으세요.
            4. 가능한 빨리 병원으로 이동하세요.
            5. 자가격리 지침을 따르세요.
            
            """.trimIndent()

        guidelinesTextView.text = guidelines
    }
}