document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('code-form');
    const resultContainer = document.getElementById('result-container');
    const resultElement = document.getElementById('execution-result');
    const errorElement = document.getElementById('execution-error');
    const statusElement = document.getElementById('execution-status');
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const code = formData.get('code');
        formData.set('code', code); // 确保提交原始代码

        fetch('/execute', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            resultContainer.classList.remove('hidden');
            
            if (data.status === 'success') {
                statusElement.textContent = 'Execution successful';
                statusElement.className = 'success';
                resultElement.textContent = data.result || 'No output';
                errorElement.textContent = '';
            } else {
                statusElement.textContent = 'Execution failed';
                statusElement.className = 'error';
                resultElement.textContent = '';
                errorElement.textContent = data.error;
            }
        })
        .catch(error => {
            resultContainer.classList.remove('hidden');
            statusElement.textContent = 'Request failed';
            statusElement.className = 'error';
            resultElement.textContent = '';
            errorElement.textContent = error.message;
        });
    });
});