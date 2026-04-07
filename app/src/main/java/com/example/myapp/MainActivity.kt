package com.example.myapp

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import android.widget.Button
import android.widget.TextView
import android.widget.Toast

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val textView = findViewById<TextView>(R.id.welcome_text)
        val button = findViewById<Button>(R.id.action_button)

        button.setOnClickListener {
            Toast.makeText(this, "Agent Initialized in Antigravity!", Toast.LENGTH_SHORT).show()
        }
    }
}
