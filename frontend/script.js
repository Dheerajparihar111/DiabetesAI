async function uploadImage() {

    const file =
        document.getElementById("imageInput").files[0]

    const formData = new FormData()

    formData.append("file", file)

    const response = await fetch(
        "http://127.0.0.1:8000/predict-image",
        {
            method: "POST",
            body: formData
        }
    )

    const data = await response.json()

    document.getElementById("result").innerHTML =
        JSON.stringify(data, null, 2)
}