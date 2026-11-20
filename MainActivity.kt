package com.jhumong.digitalhub

import android.app.Activity
import android.content.ContentValues
import android.graphics.Typeface
import android.provider.MediaStore
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.view.ViewGroup
import android.widget.*
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

// Walang external library na kailangan.
class MainActivity : Activity(), TextToSpeech.OnInitListener {

    private lateinit var urlBox: EditText
    private lateinit var log: TextView
    private lateinit var scroll: ScrollView
    private lateinit var input: EditText
    private lateinit var video: VideoView
    private lateinit var tts: TextToSpeech
    private val ui = Handler(Looper.getMainLooper())
    private var lastId: String? = null
    private val prefs by lazy { getSharedPreferences("jarvis", MODE_PRIVATE) }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        tts = TextToSpeech(this, this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0A0F1F"))
            setPadding(24, 48, 24, 24)
        }
        urlBox = EditText(this).apply {
            hint = "Colab URL (https://....trycloudflare.com)"
            setText(prefs.getString("url", ""))
            setTextColor(Color.CYAN); setHintTextColor(Color.GRAY)
            textSize = 12f; setSingleLine()
        }
        video = VideoView(this)
        log = TextView(this).apply { setTextColor(Color.WHITE); textSize = 15f }
        scroll = ScrollView(this).apply { addView(log) }
        input = EditText(this).apply {
            hint = "Utusan si JARVIS..."
            setTextColor(Color.WHITE); setHintTextColor(Color.GRAY)
        }
        val save = Button(this).apply { text = "💾"; setOnClickListener { saveToGallery() } }
        val send = Button(this).apply { text = "Send"; setOnClickListener { send(input.text.toString()) } }
        val mic = Button(this).apply { text = "🎤"; setOnClickListener { listen() } }
        val row = LinearLayout(this).apply {
            addView(input, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(mic); addView(save); addView(send)
        }

        val title = TextView(this).apply {
            text = "JHUMONG DIGITAL HUB"
            setTextColor(Color.CYAN); textSize = 20f
            typeface = Typeface.DEFAULT_BOLD
        }
        root.addView(title)
        root.addView(urlBox)
        root.addView(video, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.2f))
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        root.addView(row)
        setContentView(root)
        say("JARVIS", "Jhumong Digital Hub online na, Boss. Ako si JARVIS. Ano ang gagawin natin ngayon?")
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) tts.language = Locale("fil", "PH")
    }

    private fun say(who: String, text: String) {
        log.append("\n$who: $text\n")
        scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    private fun base() = urlBox.text.toString().trim().trimEnd('/')

    // ---------- network ----------
    private fun call(path: String, body: JSONObject? = null): JSONObject {
        val c = URL(base() + path).openConnection() as HttpURLConnection
        c.connectTimeout = 20000; c.readTimeout = 180000
        if (body != null) {
            c.requestMethod = "POST"; c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val j = JSONObject(c.inputStream.bufferedReader().readText())
        if (j.has("error") && !j.has("status")) throw Exception(j.getString("error"))
        return j
    }

    private fun download(id: String): File {
        val f = File(cacheDir, "$id.mp4")
        URL(base() + "/video/$id").openStream().use { i -> f.outputStream().use { o -> i.copyTo(o) } }
        return f
    }

    private fun waitAndPlay(id: String) {
        while (true) {
            val s = call("/status/$id")
            when (s.optString("status")) {
                "done" -> break
                "error" -> throw Exception(s.optString("error"))
            }
            Thread.sleep(3000)
        }
        val f = download(id)
        lastId = id
        ui.post {
            video.setVideoPath(f.absolutePath)
            video.setOnPreparedListener { it.isLooping = true; video.start() }
            say("JARVIS", "Tapos na, Boss.")
        }
    }

    // ---------- Jarvis loop ----------
    private fun send(text: String) {
        if (text.isBlank()) return
        prefs.edit().putString("url", base()).apply()
        say("Ikaw", text); input.setText("")
        Thread {
            try {
                val r = call("/chat", JSONObject().put("message", text).put("last_id", lastId ?: ""))
                val reply = r.optString("reply")
                ui.post { say("JARVIS", reply); tts.speak(reply, TextToSpeech.QUEUE_FLUSH, null, "j") }
                when (r.optString("action")) {
                    "generate" -> {
                        ui.post { say("JARVIS", "Gumagawa ng video... (1-3 min kada eksena)") }
                        val scenes = r.optJSONArray("scenes")
                        val body = JSONObject()
                        if (scenes != null && scenes.length() > 0) body.put("scenes", scenes)
                        else body.put("prompt", r.optString("prompt"))
                        val j = call("/generate", body)
                        waitAndPlay(j.getString("id"))
                    }
                    "edit" -> {
                        val j = call("/edit", JSONObject().put("id", lastId ?: "").put("edit", r.getJSONObject("edit")))
                        waitAndPlay(j.getString("id"))
                    }
                }
            } catch (e: Exception) {
                ui.post { say("Error", e.message ?: "may problema") }
            }
        }.start()
    }

    // ---------- i-save sa Gallery para ma-upload sa FB/YouTube ----------
    private fun saveToGallery() {
        val f = lastId?.let { File(cacheDir, "$it.mp4") }
        if (f == null || !f.exists()) { say("JARVIS", "Wala pang video, Boss."); return }
        val v = ContentValues().apply {
            put(MediaStore.Video.Media.DISPLAY_NAME, "Jhumong_${f.nameWithoutExtension}.mp4")
            put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
            put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/JhumongDigitalHub")
        }
        val uri = contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, v)
        if (uri == null) { say("Error", "Hindi ma-save"); return }
        contentResolver.openOutputStream(uri)?.use { o -> f.inputStream().use { it.copyTo(o) } }
        say("JARVIS", "Na-save sa Gallery (Movies/JhumongDigitalHub). Pwede mo nang i-upload sa Facebook o YouTube.")
    }

    // ---------- boses ----------
    private fun listen() {
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fil-PH")
        }
        try { startActivityForResult(i, 1) } catch (e: Exception) { say("Error", "Walang speech service") }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        super.onActivityResult(req, res, data)
        if (req == 1 && res == RESULT_OK) {
            data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { send(it) }
        }
    }

    override fun onDestroy() { tts.shutdown(); super.onDestroy() }
}
