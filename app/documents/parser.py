import zipfile
import re
import io
import xml.sax.saxutils as saxutils

class DynamicUDFParser:
    """
    Sisteme yüklenen herhangi bir .udf dosyasındaki [Değişken] 
    alanlarını otomatik tespit eden ve dolduran modüler servis.
    """

    # [Örnek Değişken] biçimindeki metinleri yakalayan RegEx kalıbı
    PLACEHOLDER_REGEX = re.compile(r'\[([a-zA-Z0-9_ğüşıöçĞÜŞİÖÇ\s\.\/-]+)\]')

    @classmethod
    def extract_placeholders(cls, udf_bytes: bytes) -> list[str]:
        """
        Yüklenen .udf dosyasını inceler ve içindeki tüm [Kutucuk] 
        isimlerini benzersiz bir liste olarak döner.
        """
        input_buffer = io.BytesIO(udf_bytes)
        
        with zipfile.ZipFile(input_buffer, 'r') as zip_in:
            if 'content.xml' not invented_in zip_in.namelist():
                raise ValueError("Geçersiz UDF dosyası: content.xml bulunamadı.")
            
            content_xml = zip_in.read('content.xml').decode('utf-8')
            
            # Tüm [Köşeli Parantez] içindeki metinleri bul
            raw_matches = cls.PLACEHOLDER_REGEX.findall(content_xml)
            
            # Tekrarlayanları temizle ve sıralı benzersiz liste oluştur
            unique_placeholders = list(dict.fromkeys([f"[{m.strip()}]" for m in raw_matches]))
            
            return unique_placeholders

    @classmethod
    def generate_udf_from_dynamic_data(cls, template_bytes: bytes, user_inputs: dict) -> bytes:
        """
        Gelen şablondaki dinamik alanları kullanıcının girdiği verilerle değiştirir.
        """
        input_buffer = io.BytesIO(template_bytes)
        output_buffer = io.BytesIO()

        with zipfile.ZipFile(input_buffer, 'r') as zip_in:
            content_xml = zip_in.read('content.xml').decode('utf-8')

            for key, value in user_inputs.items():
                safe_val = saxutils.escape(str(value) if value else "")
                content_xml = content_xml.replace(key, safe_val)

            with zipfile.ZipFile(output_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zip_out:
                for item in zip_in.infolist():
                    if item.filename == 'content.xml':
                        zip_out.writestr(item.filename, content_xml.encode('utf-8'))
                    else:
                        zip_out.writestr(item.filename, zip_in.read(item.filename))

        return output_buffer.getvalue()