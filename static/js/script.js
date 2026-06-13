document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const fileInput = document.getElementById('imageUpload');
    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append('image', file);

    fetch('/detect', {
        method: 'POST',
        body: formData
    }).then(response => response.json())
      .then(data => {
        document.getElementById('resultImage').src = data.result_image_url;
        document.getElementById('resultImage').style.display = 'block';
        document.getElementById('resultPlaceholder').style.display = 'none';

        document.getElementById('tumorProbability').innerHTML = '检测到肿瘤概率: <span class="fw-bold">' + data.tumor_probability + '</span>';
        document.getElementById('tumorLocation').innerHTML = '肿瘤位置: <span class="fw-bold">' + data.tumor_location + '</span>';
        document.getElementById('tumorSize').innerHTML = '肿瘤大小: <span class="fw-bold">' + data.tumor_size + '</span>';
        document.getElementById('resultDetails').style.display = 'block';
    });
});

