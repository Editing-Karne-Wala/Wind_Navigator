package com.example.myapp;

import android.content.Intent;
import android.os.Bundle;
import android.text.method.PasswordTransformationMethod;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public class LoginActivity extends AppCompatActivity {

    EditText email;
    EditText password;
    Button login;
    TextView reglink;
    static String registeredName = "Abhinav";
    static String registeredEmail = "abhinav208000@gmail.com";
    static String registeredPass = "123456789";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        email = findViewById(R.id.email);
        password = findViewById(R.id.password);
        login = findViewById(R.id.login);
        reglink = findViewById(R.id.reglink);

        password.setTransformationMethod(PasswordTransformationMethod.getInstance());

        Retrofit retrofit = new Retrofit.Builder()
                .baseUrl("https://api.genderize.io/")
                .addConverterFactory(GsonConverterFactory.create())
                .build();

        GenderApi api = retrofit.create(GenderApi.class);

        login.setOnClickListener(v -> {
            String userEmail = email.getText().toString();
            String userPass = password.getText().toString();
            if (userEmail.equals(registeredEmail) && userPass.equals(registeredPass)) {
                
                api.getGender(registeredName).enqueue(new Callback<GenderApi.GenderResponse>() {
                    @Override
                    public void onResponse(Call<GenderApi.GenderResponse> call, Response<GenderApi.GenderResponse> response) {
                        if (response.isSuccessful() && response.body() != null) {
                            reglink.setText("Login Success - Gender: " + response.body().gender);
                        }
                    }

                    @Override
                    public void onFailure(Call<GenderApi.GenderResponse> call, Throwable t) {
                        reglink.setText("Login Success - Gender: Unknown");
                    }
                });
            } else {
                reglink.setText("Login Failed");
            }
        });

        reglink.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent intent = new Intent(LoginActivity.this, RegistrationActivity.class);
                startActivity(intent);
            }
        });
    }
}
