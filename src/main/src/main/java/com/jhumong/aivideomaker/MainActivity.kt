package com.jhumong.aivideomaker

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply {
            text = "Jhumong AI Video Maker"
            textSize = 24f
            setPadding(48, 96, 48, 48)
        })
    }
}
