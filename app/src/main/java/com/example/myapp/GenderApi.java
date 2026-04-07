package com.example.myapp;

import com.google.gson.annotations.SerializedName;
import retrofit2.Call;
import retrofit2.http.GET;
import retrofit2.http.Query;

public interface GenderApi {
    @GET("/")
    Call<GenderResponse> getGender(@Query("name") String name);

    class GenderResponse {
        @SerializedName("gender")
        public String gender;
    }
}
