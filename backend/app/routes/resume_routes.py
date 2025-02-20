from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pymongo import MongoClient
from gridfs import GridFS
from bson import ObjectId
import traceback
from io import BytesIO
# from pymongo.errors import InvalidId
from bson.errors import InvalidId  # ✅ Correct import

router = APIRouter()

# ✅ MongoDB Connection
try:
    client = MongoClient("mongodb+srv://kondasaikrishna13:W26yfBzEOZPjMkdC@cluster0.ij6bm.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    db = client["resume_db"]
    fs = GridFS(db)  # GridFS instance for file storage
    resume_collection = db["resumes"]
    print("✅ MongoDB Connected Successfully")
except Exception as e:
    print("❌ MongoDB Connection Failed:", str(e))


# ✅ Upload Resume (Prevents Duplicate Filenames)
@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    try:
        print(f"📂 Uploading file: {file.filename}")

        # ✅ Check if file with the same name already exists
        existing_resume = resume_collection.find_one({"filename": file.filename})
        if existing_resume:
            raise HTTPException(status_code=400, detail="File with the same name already exists")

        # ✅ Store file in GridFS
        file_id = fs.put(file.file, filename=file.filename)
        print(f"✅ File stored in GridFS with ID: {file_id}")

        # ✅ Insert resume metadata into MongoDB
        resume_data = {
            "filename": file.filename,
            "file_id": str(file_id)  # Convert ObjectId to string
        }
        inserted = resume_collection.insert_one(resume_data)
        print(f"✅ Metadata inserted into MongoDB with ID: {inserted.inserted_id}")

        return JSONResponse(content={
            "message": "File uploaded successfully",
            "file_id": str(file_id),
            "inserted_id": str(inserted.inserted_id)
        })

    except Exception as e:
        print("❌ Error during file upload:", str(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ✅ Fetch All Resumes
@router.get("/resumes")
async def get_resumes():
    try:
        resumes = resume_collection.find()
        resume_list = [
            {
                "_id": str(resume["_id"]),
                "filename": resume["filename"],
                "file_id": resume["file_id"]
            }
            for resume in resumes
        ]
        return {"resumes": resume_list}

    except Exception as e:
        print("❌ Error fetching resumes:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ✅ View Resume Details (Validates ObjectId Format)
@router.get("/resume/{resume_id}")
async def get_resume(resume_id: str):
    try:
        if not ObjectId.is_valid(resume_id):
            raise HTTPException(status_code=400, detail="Invalid resume ID format")

        resume = resume_collection.find_one({"_id": ObjectId(resume_id)})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        return {
            "_id": str(resume["_id"]),
            "filename": resume["filename"],
            "file_id": resume["file_id"]
        }

    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    except Exception as e:
        print("❌ Error fetching resume details:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ✅ Download Resume (Validates File ID)
@router.get("/download/{file_id}")
async def download_resume(file_id: str):
    try:
        if not ObjectId.is_valid(file_id):
            raise HTTPException(status_code=400, detail="Invalid file ID format")

        file_obj = fs.get(ObjectId(file_id))
        if not file_obj:
            raise HTTPException(status_code=404, detail="File not found")

        return StreamingResponse(
            BytesIO(file_obj.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={file_obj.filename}"}
        )

    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    except Exception as e:
        print("❌ Error downloading file:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ✅ Delete Resume (Removes File from GridFS & MongoDB)


@router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str):
    try:
        if not ObjectId.is_valid(resume_id):
            raise HTTPException(status_code=400, detail="Invalid resume ID format")

        resume = resume_collection.find_one({"_id": ObjectId(resume_id)})
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        # ✅ Check if file_id exists before attempting deletion
        file_id = resume.get("file_id")
        if file_id:
            if fs.exists({"_id": ObjectId(file_id)}):
                fs.delete(ObjectId(file_id))  # ✅ Delete from GridFS

        # ✅ Delete from MongoDB
        delete_result = resume_collection.delete_one({"_id": ObjectId(resume_id)})
        if delete_result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Resume not found in database")

        return {"message": "✅ Resume deleted successfully"}

    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    except Exception as e:
        print(f"❌ Error deleting resume: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
