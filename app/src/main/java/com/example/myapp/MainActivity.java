package com.example.myapp;

import android.os.Bundle;
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    EditText email;
    EditText password;
    Button login;
    TextView forgot;
    TextView register;
    boolean isVisible = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        email = findViewById(R.id.email);
        password = findViewById(R.id.password);
        login = findViewById(R.id.login);
        forgot = findViewById(R.id.forgot);
        register = findViewById(R.id.register);

        if (isVisible == false) {
            password.setTransformationMethod(PasswordTransformationMethod.getInstance());
        } else {
            password.setTransformationMethod(HideReturnsTransformationMethod.getInstance());
        }

        login.setOnClickListener(v -> {
            String userEmail = email.getText().toString();
            String userPass = password.getText().toString();
            if (userEmail.equals("abhinav208000@gmail.com") && userPass.equals("123456789")) {
                register.setText("Login Success");
            } else {
                register.setText("Login Failed");
            }
        });
    }
}
