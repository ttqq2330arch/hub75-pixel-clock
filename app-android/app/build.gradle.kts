plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.ttqq.pixelclock"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.ttqq.pixelclock"
        // 26 = Android 8.0。用 java.util.Base64 替代 android.util.Base64，
        // 这样解码逻辑能在 JVM 单元测试里真跑（覆盖 97%+ 设备）
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            // 个人版：debug 签名即可自用，无需上架
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    // 中文路径下 Gradle test worker 解析 classpath 会失败（ClassNotFoundException），
    // 强制 test worker 用 ASCII 编码处理路径
    testOptions {
        unitTests.all {
            it.useJUnit()
            it.systemProperty("file.encoding", "UTF-8")
            // 局域网测试需要绕过本机代理：板子在 192.168.x.x，走代理会被拦
            it.systemProperty("http.nonProxyHosts", "192.168.*|10.*|172.16.*|*.local|localhost")
            it.systemProperty("https.nonProxyHosts", "192.168.*|10.*|172.16.*|*.local|localhost")
        }
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }
    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("androidx.activity:activity-compose:1.9.1")
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    testImplementation("junit:junit:4.13.2")
    // JVM 单元测试需要真实的 org.json（Android SDK 里是空壳）
    testImplementation("org.json:json:20240303")
}
