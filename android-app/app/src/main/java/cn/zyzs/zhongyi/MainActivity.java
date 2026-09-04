package cn.zyzs.zhongyi;

import android.annotation.SuppressLint;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private static final String HOME_URL = "https://zhongyi.9yzs.cn/%E4%B8%AD%E8%8D%AF%E5%AD%A6%E4%B9%A0%E5%AE%9D%E5%85%B8.html";

    private WebView webView;
    private SwipeRefreshLayout refresh;
    private View errorView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#f5f0e6"));

        refresh = new SwipeRefreshLayout(this);
        refresh.setColorSchemeColors(Color.parseColor("#2f5d3a"));
        refresh.setOnRefreshListener(() -> loadHome());

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        refresh.addView(webView);
        root.addView(refresh);

        // 网络错误遮罩
        errorView = getLayoutInflater().inflate(R.layout.error_view, root, false);
        errorView.findViewById(R.id.btn_retry).setOnClickListener(v -> loadHome());
        errorView.setVisibility(View.GONE);
        root.addView(errorView);

        setContentView(root);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                refresh.setRefreshing(false);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    showError();
                }
            }
        });
        webView.setWebChromeClient(new WebChromeClient());

        // 网页弹层开关回调：弹层打开时禁用下拉刷新，否则 WebView 会拦截弹层内滑动
        webView.addJavascriptInterface(new NativeBridge(), "NativeBridge");

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack();
                } else {
                    finish();
                }
            }
        });

        loadHome();
    }

    private void loadHome() {
        errorView.setVisibility(View.GONE);
        if (!isNetworkAvailable()) {
            showError();
            return;
        }
        webView.loadUrl(HOME_URL);
    }

    private void showError() {
        refresh.setRefreshing(false);
        errorView.setVisibility(View.VISIBLE);
    }

    private class NativeBridge {
        @JavascriptInterface
        public void setOverlayOpen(boolean open) {
            runOnUiThread(() -> refresh.setEnabled(!open));
        }
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        NetworkInfo info = cm.getActiveNetworkInfo();
        return info != null && info.isConnected();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
