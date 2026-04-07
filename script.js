const xmlCode = `<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout
    xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    tools:context=".MainActivity">

    <TextView
        android:id="@+id/textView"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Hello, Antigravity!"
        android:textSize="24sp"
        android:textColor="@color/black"
        app:layout_constraintBottom_toBottomOf="parent"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent"
        app:layout_constraintTop_toTopOf="parent" />

    <Button
        android:id="@+id/button"
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Execute Task"
        android:layout_marginTop="16dp"
        app:layout_constraintTop_toBottomOf="@+id/textView"
        app:layout_constraintEnd_toEndOf="parent"
        app:layout_constraintStart_toStartOf="parent" />

</androidx.constraintlayout.widget.ConstraintLayout>`;

function highlightXML(code) {
    return code
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/(&lt;\?xml.*?\?&gt;)/g, '<span class="code-comment">$1</span>')
        .replace(/(&lt;\/?[\w:.-]+)/g, '<span class="code-tag">$1</span>')
        .replace(/([\w:.-]+)(?==)/g, '<span class="code-attr">$1</span>')
        .replace(/"(.*?)"/g, '<span class="code-val">"$1"</span>')
        .replace(/(&gt;)/g, '<span class="code-tag">$1</span>');
}

function initEditor() {
    const codeContent = document.getElementById('code-content');
    const lineNumbers = document.getElementById('line-numbers');

    const highlighted = highlightXML(xmlCode);
    codeContent.innerHTML = highlighted;

    const lines = xmlCode.split('\n').length;
    let numbers = '';
    for (let i = 1; i <= lines; i++) {
        numbers += i + '<br>';
    }
    lineNumbers.innerHTML = numbers;
}

document.addEventListener('DOMContentLoaded', initEditor);
